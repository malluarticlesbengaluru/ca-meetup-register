// Edge Function "photos" - the only thing that ever holds the Storj keys. Paste this whole file into
// Supabase > Edge Functions > photos (see PHOTOS_SETUP.md). The browser never sees a Storj key.
//
// What it does (all POST, JSON):
//   action "reserve"  claim space in the database (the database decides: limits, Present, pools), then hand back a
//                     short-lived upload address for exactly that one file.
//   action "confirm"  ask Storj for the file's REAL size; the database keeps it only if it is not bigger than claimed
//                     (a bigger file is deleted). Saves the tiny preview picture.
//   action "fail"     the upload did not happen: free the claim.
//   action "preview"  short-lived address of the SHARP preview (about 1600 pixels, saved next to the photo as "<key>.p.jpg") for one
//                     photo, only if the database says this login may see that photo. Originals are never given out here.
//   actions "vreserve", "vconfirm", "vfail", "vpreview", "vview", "vremove", "vexport": the same for ATTENDEE VIDEOS, kept in a third
//                     Storj account (STORJ_VID_*), under "video/...". Nobody plays a video on the site: "vpreview" gives only the sharp
//                     still picture, "vview" (the original) only to the admins whose photo_download switch is on.
//   action "view"     (only the admins whose "photo_download" switch is on) short-lived download address for one original.
//   action "remove"   (admin: any photo; photographer or attendee: only their own) take a photo out and delete the file.
//   action "export"   (same admins) list stored photos (key, size) with fresh download addresses, for "download everything".
//
// Secrets to set (Edge Functions > Secrets): STORJ_ACCESS_KEY, STORJ_SECRET_KEY, STORJ_BUCKET (photographers' account) and, if the
// public gets its own Storj account, STORJ_PUB_ACCESS_KEY, STORJ_PUB_SECRET_KEY, STORJ_PUB_BUCKET. (SUPABASE_URL and
// SUPABASE_SERVICE_ROLE_KEY are provided by Supabase automatically.)
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";
import { AwsClient } from "https://esm.sh/aws4fetch@1.0.20";

const ENDPOINT = Deno.env.get("STORJ_ENDPOINT") || "https://gateway.storjshare.io";
// Two storage accounts are supported: the photographers' one (STORJ_*) and, optionally, a separate one for the public
// (STORJ_PUB_*). A photo's place is told by its key: "camera/..." goes to the photographers' account, "public/..." to the
// public account. If the STORJ_PUB_* secrets are not set, everything uses the photographers' account (one account only).
// Videos use a third account (STORJ_VID_ACCESS_KEY, STORJ_VID_SECRET_KEY, STORJ_VID_BUCKET); without those secrets, video actions answer NOT_CONFIGURED.
// SHARED ATTENDEE SPACE (r2_32): when the admin switches it on, attendee photos AND videos may go to any of three attendee accounts, chosen by the
// database (the one holding the least): key "att/1/..." = the public account (STORJ_PUB_*), "att/2/..." = the video account (STORJ_VID_*),
// "att/3/..." = a fourth account (STORJ_ATT_ACCESS_KEY, STORJ_ATT_SECRET_KEY, STORJ_ATT_BUCKET), "att/4/..." = a fifth (STORJ_ATT2_ACCESS_KEY, STORJ_ATT2_SECRET_KEY, STORJ_ATT2_BUCKET). Older keys (public/, video/) keep working.
// This function tells the database which of the four exist (accounts()), so a missing secret can never receive a file.
type Acct = { bucket: string; aws: AwsClient };
const mk = (bucket: string, id: string, secret: string): Acct => ({
  bucket, aws: new AwsClient({ accessKeyId: id, secretAccessKey: secret, service: "s3", region: "us-1" }),
});
const CAM: Acct = mk(Deno.env.get("STORJ_BUCKET") || "", Deno.env.get("STORJ_ACCESS_KEY") || "", Deno.env.get("STORJ_SECRET_KEY") || "");
const PUB: Acct = Deno.env.get("STORJ_PUB_BUCKET") && Deno.env.get("STORJ_PUB_ACCESS_KEY") && Deno.env.get("STORJ_PUB_SECRET_KEY")
  ? mk(Deno.env.get("STORJ_PUB_BUCKET")!, Deno.env.get("STORJ_PUB_ACCESS_KEY")!, Deno.env.get("STORJ_PUB_SECRET_KEY")!)
  : CAM;
const VID: Acct | null = Deno.env.get("STORJ_VID_BUCKET") && Deno.env.get("STORJ_VID_ACCESS_KEY") && Deno.env.get("STORJ_VID_SECRET_KEY")
  ? mk(Deno.env.get("STORJ_VID_BUCKET")!, Deno.env.get("STORJ_VID_ACCESS_KEY")!, Deno.env.get("STORJ_VID_SECRET_KEY")!)
  : null;
const ATT: Acct | null = Deno.env.get("STORJ_ATT_BUCKET") && Deno.env.get("STORJ_ATT_ACCESS_KEY") && Deno.env.get("STORJ_ATT_SECRET_KEY")
  ? mk(Deno.env.get("STORJ_ATT_BUCKET")!, Deno.env.get("STORJ_ATT_ACCESS_KEY")!, Deno.env.get("STORJ_ATT_SECRET_KEY")!)
  : null;
const ATT2: Acct | null = Deno.env.get("STORJ_ATT2_BUCKET") && Deno.env.get("STORJ_ATT2_ACCESS_KEY") && Deno.env.get("STORJ_ATT2_SECRET_KEY")
  ? mk(Deno.env.get("STORJ_ATT2_BUCKET")!, Deno.env.get("STORJ_ATT2_ACCESS_KEY")!, Deno.env.get("STORJ_ATT2_SECRET_KEY")!)
  : null;
// the attendee accounts that really exist, as numbers the database understands (1 = public, 2 = video, 3 and 4 = the new ones)
const accounts = (): number[] => [1, ...(VID ? [2] : []), ...(ATT ? [3] : []), ...(ATT2 ? [4] : [])];
const acct = (key: string): Acct => {
  if (key.startsWith("att/1/")) return PUB;
  if (key.startsWith("att/2/")) { if (!VID) throw new Error("NO_VIDEO_ACCOUNT"); return VID; }
  if (key.startsWith("att/3/")) { if (!ATT) throw new Error("NO_ATT_ACCOUNT"); return ATT; }
  if (key.startsWith("att/4/")) { if (!ATT2) throw new Error("NO_ATT2_ACCOUNT"); return ATT2; }
  if (key.startsWith("video/")) { if (!VID) throw new Error("NO_VIDEO_ACCOUNT"); return VID; }   // a video never lands in a photo account
  return key.startsWith("public/") ? PUB : CAM;
};
const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, content-type, apikey, x-client-info",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const out = (o: unknown, status = 200) => new Response(JSON.stringify(o), { status, headers: { ...CORS, "Content-Type": "application/json" } });

const objUrl = (key: string) => `${ENDPOINT}/${acct(key).bucket}/${key.split("/").map(encodeURIComponent).join("/")}`;
async function presign(method: string, key: string, secs: number) {
  const u = new URL(objUrl(key));
  u.searchParams.set("X-Amz-Expires", String(secs));
  const s = await acct(key).aws.sign(u.toString(), { method, aws: { signQuery: true } });
  return s.url;
}
async function head(key: string): Promise<number | null> {
  const r = await acct(key).aws.fetch(objUrl(key), { method: "HEAD" });
  if (!r.ok) return null;
  const n = Number(r.headers.get("content-length"));
  return Number.isFinite(n) && n > 0 ? n : null;
}
const PV = ".p.jpg";              // the sharp preview of a photo lives at <photo key> + PV
const PV_MAX = 2097152;           // a preview over 2 MB is not kept
// deletes the photo and its sharp preview (deleting a preview that does not exist is harmless)
async function del(key: string) {
  for (const k of [key, key + PV]) { try { await acct(k).aws.fetch(objUrl(k), { method: "DELETE" }); } catch (_) { /* the database already forgot it */ } }
}

// who is calling? returns the user id of a signed-in login, or null
async function who(req: Request): Promise<string | null> {
  const t = (req.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
  if (!t) return null;
  const { data, error } = await admin.auth.getUser(t);
  return error || !data?.user ? null : data.user.id;
}
async function mayDownload(uid: string): Promise<boolean> {
  const { data } = await admin.rpc("photo_may_download", { p_user: uid });
  return data === true;
}
async function role(uid: string): Promise<string | null> {
  const { data } = await admin.from("staff").select("role").eq("user_id", uid).maybeSingle();
  return data?.role ?? null;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: CORS });
  if (req.method !== "POST") return out({ ok: false, error: "BAD_METHOD" }, 405);
  if (!CAM.bucket) return out({ ok: false, error: "NOT_CONFIGURED" }, 500);
  let b: any; try { b = await req.json(); } catch { return out({ ok: false, error: "BAD_JSON" }, 400); }
  const action = String(b.action || "");

  try {
    if (action === "reserve") {
      const kind = b.kind === "camera" ? "camera" : "public";
      let uid: string | null = null;
      if (kind === "camera") {
        uid = await who(req);
        if (!uid) return out({ ok: false, error: "NOT_ALLOWED" }, 401);
      }
      const bytes = Math.floor(Number(b.bytes));
      const { data, error } = await admin.rpc("photo_reserve", {
        p_kind: kind, p_user: uid, p_code: kind === "public" ? String(b.code || "") : null,
        p_phone: kind === "public" ? String(b.phone || "") : null, p_bytes: bytes, p_ext: String(b.ext || ""), p_acc: accounts(),
      });
      if (error) return out({ ok: false, error: "SERVER" }, 500);
      if (!data?.ok) return out(data);
      const url = await presign("PUT", data.key, 1200);
      // the page may also send a sharp preview; its size (pbytes) was already counted inside bytes
      const pb = Math.floor(Number(b.pbytes));
      const preview_url = pb > 0 && pb <= PV_MAX && pb < bytes ? await presign("PUT", data.key + PV, 1200) : null;
      return out({ ok: true, id: data.id, url, preview_url, left_bytes: data.left_bytes });
    }

    if (action === "confirm") {
      const id = String(b.id || "");
      const { data: row } = await admin.from("photos").select("object_key,status").eq("id", id).maybeSingle();
      if (!row) return out({ ok: false, error: "NOT_FOUND" });
      const actual = await head(row.object_key);
      if (actual === null) { await admin.rpc("photo_fail", { p_id: id }); return out({ ok: false, error: "NOT_UPLOADED" }); }
      // only a plain base64 jpeg/png/webp picture is kept as the preview (anything else could carry markup)
      const thumb = typeof b.thumb === "string" && b.thumb.length <= 80000 && /^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+\/=]+$/.test(b.thumb) ? b.thumb : null;
      // the sharp preview is optional: use it only if it really arrived and is small enough; it counts toward the space used
      let pv = await head(row.object_key + PV);
      if (pv !== null && pv > PV_MAX) { try { await acct(row.object_key + PV).aws.fetch(objUrl(row.object_key + PV), { method: "DELETE" }); } catch (_) { /* ignore */ } pv = null; }
      const { data, error } = await admin.rpc("photo_confirm", { p_id: id, p_actual: actual + (pv ?? 0), p_thumb: thumb, p_preview: pv });
      if (error) return out({ ok: false, error: "SERVER" }, 500);
      if (!data?.ok && data?.key) await del(data.key);          // bigger than claimed, or too late: remove the file
      return out(data);
    }

    if (action === "fail") {
      const id = String(b.id || "");
      const { data: row } = await admin.from("photos").select("object_key,status").eq("id", id).maybeSingle();
      if (row && row.status === "reserved") { await admin.rpc("photo_fail", { p_id: id }); await del(row.object_key); }
      return out({ ok: true });
    }

    // ---- attendee videos (third Storj account) ----
    if (action.startsWith("v") && action !== "view") {
      if (!VID) return out({ ok: false, error: "NOT_CONFIGURED" }, 500);
      const code = String(b.code || ""), phone = String(b.phone || "");

      if (action === "vreserve") {
        const bytes = Math.floor(Number(b.bytes));
        const { data, error } = await admin.rpc("video_reserve", { p_code: code, p_phone: phone, p_bytes: bytes, p_ext: String(b.ext || ""), p_acc: accounts() });
        if (error) return out({ ok: false, error: "SERVER" }, 500);
        if (!data?.ok) return out(data);
        const url = await presign("PUT", data.key, 1800);
        const pb = Math.floor(Number(b.pbytes));
        const preview_url = pb > 0 && pb <= PV_MAX && pb < bytes ? await presign("PUT", data.key + PV, 1800) : null;
        return out({ ok: true, id: data.id, url, preview_url, left_bytes: data.left_bytes });
      }

      if (action === "vconfirm") {
        const id = String(b.id || "");
        const { data: row } = await admin.from("videos").select("object_key,status").eq("id", id).maybeSingle();
        if (!row) return out({ ok: false, error: "NOT_FOUND" });
        const actual = await head(row.object_key);
        if (actual === null) { await admin.rpc("video_fail", { p_id: id }); return out({ ok: false, error: "NOT_UPLOADED" }); }
        const thumb = typeof b.thumb === "string" && b.thumb.length <= 80000 && /^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+\/=]+$/.test(b.thumb) ? b.thumb : null;
        let pv = await head(row.object_key + PV);
        if (pv !== null && pv > PV_MAX) { try { await acct(row.object_key + PV).aws.fetch(objUrl(row.object_key + PV), { method: "DELETE" }); } catch (_) { /* ignore */ } pv = null; }
        const { data, error } = await admin.rpc("video_confirm", { p_id: id, p_actual: actual + (pv ?? 0), p_thumb: thumb, p_preview: pv });
        if (error) return out({ ok: false, error: "SERVER" }, 500);
        if (!data?.ok && data?.key) await del(data.key);
        return out(data);
      }

      if (action === "vfail") {
        const id = String(b.id || "");
        const { data: row } = await admin.from("videos").select("object_key,status").eq("id", id).maybeSingle();
        if (row && row.status === "reserved") { await admin.rpc("video_fail", { p_id: id }); await del(row.object_key); }
        return out({ ok: true });
      }

      if (action === "vpreview") {
        const id = String(b.id || "");
        const uid = await who(req);
        const { data: key } = uid
          ? await admin.rpc("video_preview_key", { p_id: id, p_user: uid, p_code: null, p_phone: null })
          : await admin.rpc("video_preview_key", { p_id: id, p_user: null, p_code: code, p_phone: phone });
        if (!key) return out({ ok: false, error: "NOT_FOUND" });
        return out({ ok: true, url: await presign("GET", String(key), 600) });
      }

      if (action === "vremove") {
        const id = String(b.id || "");
        const uid = await who(req);
        if (uid) {
          if ((await role(uid)) !== "admin") return out({ ok: false, error: "NOT_ALLOWED" }, 401);
          const asUser = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, {
            auth: { persistSession: false }, global: { headers: { Authorization: req.headers.get("authorization") || "" } } });
          const { data: key, error } = await asUser.rpc("admin_video_remove", { p_id: id });
          if (error || !key) return out({ ok: false, error: "NOT_FOUND" });
          await del(String(key));
          return out({ ok: true });
        }
        const { data: key } = await admin.rpc("video_remove_public", { p_id: id, p_code: code, p_phone: phone });
        if (!key) return out({ ok: false, error: "NOT_FOUND" });
        await del(String(key));
        return out({ ok: true });
      }

      // the rest: only admins whose photo_download switch is on
      const uid = await who(req);
      if (!uid || !(await mayDownload(uid))) return out({ ok: false, error: "NOT_ALLOWED" }, 401);
      if (action === "vview") {
        const { data: key } = await admin.rpc("video_original_key", { p_id: String(b.id || ""), p_user: uid });
        if (!key) return out({ ok: false, error: "NOT_FOUND" });
        return out({ ok: true, url: await presign("GET", String(key), 600) });
      }
      if (action === "vexport") {
        const from = Math.max(0, Math.floor(Number(b.from) || 0));
        const { data: rows } = await admin.from("videos").select("id,object_key,bytes_actual,created_at")
          .eq("status", "stored").order("created_at").range(from, from + 49);
        const list = [];
        for (const r of rows || []) list.push({ id: r.id, kind: "video", key: r.object_key, bytes: r.bytes_actual, url: await presign("GET", r.object_key, 3600) });
        return out({ ok: true, items: list, next: (rows || []).length === 50 ? from + 50 : null });
      }
      return out({ ok: false, error: "BAD_ACTION" }, 400);
    }

    // ---- preview: the sharp picture, for whoever the database says may see this photo ----
    if (action === "preview") {
      const id = String(b.id || "");
      const uid = await who(req);
      const { data: key } = uid
        ? await admin.rpc("photo_preview_key", { p_id: id, p_user: uid, p_code: null, p_phone: null })
        : await admin.rpc("photo_preview_key", { p_id: id, p_user: null, p_code: String(b.code || ""), p_phone: String(b.phone || "") });
      if (!key) return out({ ok: false, error: "NOT_FOUND" });
      return out({ ok: true, url: await presign("GET", String(key), 600) });
    }

    // ---- view (admin only) and remove (an admin, or a photographer / attendee for their own photo) ----
    if (action === "view") {
      // only an admin whose photo_download switch is on may download an original (checked here and again inside photo_original_key)
      const uid = await who(req);
      if (!uid) return out({ ok: false, error: "NOT_ALLOWED" }, 401);
      if (!(await mayDownload(uid))) return out({ ok: false, error: "NOT_ALLOWED" }, 403);
      const { data: key } = await admin.rpc("photo_original_key", { p_id: String(b.id || ""), p_user: uid });
      if (!key) return out({ ok: false, error: "NOT_FOUND" });
      return out({ ok: true, url: await presign("GET", String(key), 600) });
    }

    if (action === "remove") {
      const id = String(b.id || "");
      const uid = await who(req);
      if (uid) {
        const rl = await role(uid);
        if (rl === "admin") {
          // run as the admin themselves, so the database checks it and writes the Settings log entry
          const asUser = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, {
            auth: { persistSession: false }, global: { headers: { Authorization: req.headers.get("authorization") || "" } } });
          const { data: key, error } = await asUser.rpc("admin_photo_remove", { p_id: id });
          if (error || !key) return out({ ok: false, error: "NOT_FOUND" });
          await del(String(key));
          return out({ ok: true });
        }
        if (rl === "camera") {
          const { data: key } = await admin.rpc("photo_remove_camera", { p_id: id, p_user: uid });
          if (!key) return out({ ok: false, error: "NOT_FOUND" });
          await del(String(key));
          return out({ ok: true });
        }
        return out({ ok: false, error: "NOT_ALLOWED" }, 401);
      }
      // an attendee removing their own photo: Booking ID + phone, checked by the database
      const { data: key } = await admin.rpc("photo_remove_public", { p_id: id, p_code: String(b.code || ""), p_phone: String(b.phone || "") });
      if (!key) return out({ ok: false, error: "NOT_FOUND" });
      await del(String(key));
      return out({ ok: true });
    }

    // ---- "download everything": only admins whose photo_download switch is on ----
    const uid = await who(req);
    if (!uid || !(await mayDownload(uid))) return out({ ok: false, error: "NOT_ALLOWED" }, 401);

    if (action === "export") {
      const from = Math.max(0, Math.floor(Number(b.from) || 0));
      const { data: rows } = await admin.from("photos").select("id,kind,object_key,bytes_actual,created_at")
        .eq("status", "stored").order("created_at").range(from, from + 49);
      const list = [];
      for (const r of rows || []) list.push({ id: r.id, kind: r.kind, key: r.object_key, bytes: r.bytes_actual, url: await presign("GET", r.object_key, 3600) });
      return out({ ok: true, items: list, next: (rows || []).length === 50 ? from + 50 : null });
    }

    return out({ ok: false, error: "BAD_ACTION" }, 400);
  } catch (_e) {
    return out({ ok: false, error: "SERVER" }, 500);
  }
});

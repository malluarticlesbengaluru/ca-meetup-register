// Edge Function "photos" - the only thing that ever holds the Storj keys. Paste this whole file into
// Supabase > Edge Functions > photos (see PHOTOS_SETUP.md). The browser never sees a Storj key.
//
// What it does (all POST, JSON):
//   action "reserve"  claim space in the database (the database decides: limits, Present, pools), then hand back a
//                     short-lived upload address for exactly that one file.
//   action "confirm"  ask Storj for the file's REAL size; the database keeps it only if it is not bigger than claimed
//                     (a bigger file is deleted). Saves the tiny preview picture.
//   action "fail"     the upload did not happen: free the claim.
//   action "view"     (admin or photographer) short-lived download address for one original; the database decides which.
//   action "remove"   (admin: any photo; photographer or attendee: only their own) take a photo out and delete the file.
//   action "export"   (admin) list stored photos (key, size) with fresh download addresses, for "download everything".
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
type Acct = { bucket: string; aws: AwsClient };
const mk = (bucket: string, id: string, secret: string): Acct => ({
  bucket, aws: new AwsClient({ accessKeyId: id, secretAccessKey: secret, service: "s3", region: "us-1" }),
});
const CAM: Acct = mk(Deno.env.get("STORJ_BUCKET") || "", Deno.env.get("STORJ_ACCESS_KEY") || "", Deno.env.get("STORJ_SECRET_KEY") || "");
const PUB: Acct = Deno.env.get("STORJ_PUB_BUCKET") && Deno.env.get("STORJ_PUB_ACCESS_KEY") && Deno.env.get("STORJ_PUB_SECRET_KEY")
  ? mk(Deno.env.get("STORJ_PUB_BUCKET")!, Deno.env.get("STORJ_PUB_ACCESS_KEY")!, Deno.env.get("STORJ_PUB_SECRET_KEY")!)
  : CAM;
const acct = (key: string): Acct => (key.startsWith("public/") ? PUB : CAM);
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
async function del(key: string) { try { await acct(key).aws.fetch(objUrl(key), { method: "DELETE" }); } catch (_) { /* the database already forgot it */ } }

// who is calling? returns the user id of a signed-in login, or null
async function who(req: Request): Promise<string | null> {
  const t = (req.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
  if (!t) return null;
  const { data, error } = await admin.auth.getUser(t);
  return error || !data?.user ? null : data.user.id;
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
        p_phone: kind === "public" ? String(b.phone || "") : null, p_bytes: bytes, p_ext: String(b.ext || ""),
      });
      if (error) return out({ ok: false, error: "SERVER" }, 500);
      if (!data?.ok) return out(data);
      const url = await presign("PUT", data.key, 1200);
      return out({ ok: true, id: data.id, url, left_bytes: data.left_bytes });
    }

    if (action === "confirm") {
      const id = String(b.id || "");
      const { data: row } = await admin.from("photos").select("object_key,status").eq("id", id).maybeSingle();
      if (!row) return out({ ok: false, error: "NOT_FOUND" });
      const actual = await head(row.object_key);
      if (actual === null) { await admin.rpc("photo_fail", { p_id: id }); return out({ ok: false, error: "NOT_UPLOADED" }); }
      // only a plain base64 jpeg/png/webp picture is kept as the preview (anything else could carry markup)
      const thumb = typeof b.thumb === "string" && b.thumb.length <= 80000 && /^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+\/=]+$/.test(b.thumb) ? b.thumb : null;
      const { data, error } = await admin.rpc("photo_confirm", { p_id: id, p_actual: actual, p_thumb: thumb });
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

    // ---- view and remove: an admin, a photographer, or (remove only) the attendee who owns the photo ----
    if (action === "view") {
      // the database decides which original this login may download (admin: any; photographer: own, or all if the admin allows)
      const uid = await who(req);
      if (!uid) return out({ ok: false, error: "NOT_ALLOWED" }, 401);
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

    // ---- admin only from here ----
    const uid = await who(req);
    if (!uid || (await role(uid)) !== "admin") return out({ ok: false, error: "NOT_ALLOWED" }, 401);

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

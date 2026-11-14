// Edge Function "photos" - the only thing that ever holds the Storj keys. Paste this whole file into
// Supabase > Edge Functions > photos (see PHOTOS_SETUP.md). The browser never sees a Storj key.
//
// What it does (all POST, JSON):
//   action "reserve"  claim space in the database (the database decides: limits, Present, pools), then hand back a
//                     short-lived upload address for exactly that one file.
//   action "confirm"  ask Storj for the file's REAL size; the database keeps it only if it is not bigger than claimed
//                     (a bigger file is deleted). Saves the tiny preview picture.
//   action "fail"     the upload did not happen: free the claim.
//   action "view"     (admin) short-lived download address for one original.
//   action "remove"   (admin) take a photo out and delete the file.
//   action "export"   (admin) list stored photos (key, size) with fresh download addresses, for "download everything".
//
// Secrets to set (Edge Functions > Secrets): STORJ_ACCESS_KEY, STORJ_SECRET_KEY, STORJ_BUCKET. (SUPABASE_URL and
// SUPABASE_SERVICE_ROLE_KEY are provided by Supabase automatically.)
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";
import { AwsClient } from "https://esm.sh/aws4fetch@1.0.20";

const ENDPOINT = Deno.env.get("STORJ_ENDPOINT") || "https://gateway.storjshare.io";
const BUCKET = Deno.env.get("STORJ_BUCKET") || "";
const aws = new AwsClient({
  accessKeyId: Deno.env.get("STORJ_ACCESS_KEY") || "",
  secretAccessKey: Deno.env.get("STORJ_SECRET_KEY") || "",
  service: "s3", region: "us-1",
});
const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, content-type, apikey, x-client-info",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const out = (o: unknown, status = 200) => new Response(JSON.stringify(o), { status, headers: { ...CORS, "Content-Type": "application/json" } });

const objUrl = (key: string) => `${ENDPOINT}/${BUCKET}/${key.split("/").map(encodeURIComponent).join("/")}`;
async function presign(method: string, key: string, secs: number) {
  const u = new URL(objUrl(key));
  u.searchParams.set("X-Amz-Expires", String(secs));
  const s = await aws.sign(u.toString(), { method, aws: { signQuery: true } });
  return s.url;
}
async function head(key: string): Promise<number | null> {
  const r = await aws.fetch(objUrl(key), { method: "HEAD" });
  if (!r.ok) return null;
  const n = Number(r.headers.get("content-length"));
  return Number.isFinite(n) && n > 0 ? n : null;
}
async function del(key: string) { try { await aws.fetch(objUrl(key), { method: "DELETE" }); } catch (_) { /* the database already forgot it */ } }

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
  if (!BUCKET) return out({ ok: false, error: "NOT_CONFIGURED" }, 500);
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
      const thumb = typeof b.thumb === "string" && b.thumb.startsWith("data:image/") ? b.thumb : null;
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

    // ---- admin only from here ----
    const uid = await who(req);
    if (!uid || (await role(uid)) !== "admin") return out({ ok: false, error: "NOT_ALLOWED" }, 401);

    if (action === "view") {
      const { data: row } = await admin.from("photos").select("object_key").eq("id", String(b.id || "")).eq("status", "stored").maybeSingle();
      if (!row) return out({ ok: false, error: "NOT_FOUND" });
      return out({ ok: true, url: await presign("GET", row.object_key, 600) });
    }

    if (action === "remove") {
      const id = String(b.id || "");
      // run as the admin themselves, so the database checks it and writes the Settings log entry
      const asUser = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, {
        auth: { persistSession: false }, global: { headers: { Authorization: req.headers.get("authorization") || "" } } });
      const { data: key, error } = await asUser.rpc("admin_photo_remove", { p_id: id });
      if (error || !key) return out({ ok: false, error: "NOT_FOUND" });
      await del(String(key));
      return out({ ok: true });
    }

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

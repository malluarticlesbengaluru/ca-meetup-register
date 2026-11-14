/* Shared by /camera/ (photographers) and the public Photos page. Talks only to the "photos" Edge Function;
   the file itself goes straight from the phone to the storage service. No keys live here. */
window.PhotoUp = (function () {
  var MSG = {
    PHOTOS_OFF: "Photo uploads are switched off right now.",
    NOT_ALLOWED: "This login is not allowed to upload.",
    MISMATCH: "Booking ID and phone number do not match a ticket.",
    NOT_PAID: "This booking is not confirmed yet.",
    NOT_PRESENT: "Photo upload opens once you have checked in at the gate.",
    TOO_BIG: "This photo is bigger than the allowed size for one photo.",
    PERSON_FULL: "You have used your full photo space.",
    POOL_FULL: "The shared photo space is full.",
    BAD_TYPE: "This file type is not allowed. Use a normal photo.",
    BAD_SIZE: "This file looks empty.",
    NOT_UPLOADED: "The upload did not finish. Check your internet and try again.",
    SIZE_MISMATCH: "The uploaded file was bigger than expected, so it was not kept.",
    EXPIRED: "This took too long. Try again.",
    NETWORK: "No internet or a weak signal. Try again.",
    SERVER: "Something went wrong on our side. Try again in a moment."
  };
  function say(code) { return MSG[code] || "Could not upload. Try again."; }
  function extOf(f) {
    var m = /\.([a-z0-9]+)$/i.exec(f.name || ""); var e = m ? m[1].toLowerCase() : "";
    if (!e) { var t = (f.type || "").split("/")[1] || ""; e = t === "jpeg" ? "jpg" : t; }
    return e;
  }
  function mb(n) { return n >= 1048576 * 100 ? Math.round(n / 1048576) + " MB" : (n / 1048576).toFixed(n >= 1048576 * 10 ? 0 : 1) + " MB"; }
  function bytes(n) { return n >= 1073741824 ? (n / 1073741824).toFixed(2) + " GB" : mb(n); }
  /* a tiny preview picture for the admin gallery; skipped quietly if the browser cannot decode the file */
  function thumb(file) {
    return new Promise(function (res) {
      var url; try { url = URL.createObjectURL(file); } catch (e) { return res(null); }
      var img = new Image(); var done = false;
      function fin(v) { if (done) return; done = true; try { URL.revokeObjectURL(url); } catch (e) {} res(v); }
      img.onerror = function () { fin(null); };
      img.onload = function () {
        try {
          var s = 360 / Math.max(img.naturalWidth, img.naturalHeight); if (s > 1) s = 1;
          var c = document.createElement("canvas"); c.width = Math.max(1, Math.round(img.naturalWidth * s)); c.height = Math.max(1, Math.round(img.naturalHeight * s));
          c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
          var d = c.toDataURL("image/jpeg", 0.6); fin(d.length < 70000 ? d : null);
        } catch (e) { fin(null); }
      };
      setTimeout(function () { fin(null); }, 8000);
      img.src = url;
    });
  }
  function call(cfg, body) {
    var h = { "Content-Type": "application/json", "apikey": cfg.key };
    if (cfg.token) h["Authorization"] = "Bearer " + cfg.token;
    return fetch(cfg.url + "/functions/v1/photos", { method: "POST", headers: h, body: JSON.stringify(body) })
      .then(function (r) { return r.json(); })
      .catch(function () { return { ok: false, error: "NETWORK" }; });
  }
  function put(url, file, onProg) {
    return new Promise(function (res) {
      var x = new XMLHttpRequest(); x.open("PUT", url);
      x.upload.onprogress = function (e) { if (e.lengthComputable && onProg) onProg(e.loaded / e.total); };
      x.onload = function () { res(x.status >= 200 && x.status < 300); };
      x.onerror = function () { res(false); }; x.ontimeout = function () { res(false); };
      x.timeout = 10 * 60 * 1000; x.send(file);
    });
  }
  /* cfg: {url, key, token?}   who: {kind:"camera"} or {kind:"public", code, phone}.
     Resolves {ok:true, left_bytes} or {ok:false, error, message}. */
  function upload(cfg, who, file, onProg) {
    var fail = function (e) { return { ok: false, error: e, message: say(e) }; };
    var th = thumb(file);
    var body = { action: "reserve", kind: who.kind, bytes: file.size, ext: extOf(file) };
    if (who.kind === "public") { body.code = who.code; body.phone = who.phone; }
    return call(cfg, body).then(function (r) {
      if (!r.ok) return fail(r.error);
      var attempt = function (n) {
        return put(r.url, file, onProg).then(function (ok) {
          if (ok) return true; if (n >= 2) return false;
          return new Promise(function (w) { setTimeout(w, 1500 * (n + 1)); }).then(function () { return attempt(n + 1); });
        });
      };
      return attempt(0).then(function (ok) {
        if (!ok) { call(cfg, { action: "fail", id: r.id }); return fail("NETWORK"); }
        return th.then(function (t) {
          return call(cfg, { action: "confirm", id: r.id, thumb: t }).then(function (c) {
            return c.ok ? { ok: true, left_bytes: r.left_bytes } : fail(c.error);
          });
        });
      });
    });
  }
  return { upload: upload, say: say, mb: mb, bytes: bytes, call: call };
})();

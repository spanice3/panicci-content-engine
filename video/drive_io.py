#!/usr/bin/env python3
"""Google Drive I/O for the Clipper Agent (drive.file scope, stdlib only).

Auth comes from the environment, never arguments, so tokens stay out of shell history and logs:
  GDRIVE_ACCESS_TOKEN (a ~1h token; what the Clipper Agent uses), or
  GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET, GDRIVE_REFRESH_TOKEN (local use)

  python3 drive_io.py pull <shoot_folder_id> <dest_dir>
      Downloads every file in <shoot>/raw into dest_dir. Prints a JSON list of {id, name, path, size}.
  python3 drive_io.py push <src_dir> <shoot_folder_id> [--into cuts]
      Uploads src_dir (keeping its subfolders) into <shoot>/<into>/. Prints JSON {folder_id, folder_url, files:[...]}.
"""
import json, os, sys, time, urllib.parse, urllib.request, urllib.error

DRIVE = "https://www.googleapis.com/drive/v3"
UPLOAD = "https://www.googleapis.com/upload/drive/v3"
FOLDER = "application/vnd.google-apps.folder"
CHUNK = 32 * 256 * 1024  # 8 MB, a multiple of 256 KB as Drive requires
_tok = {"value": None, "at": 0.0}


def token():
    # Preferred: a short-lived access token minted elsewhere (the Clipper Agent gets one from the database),
    # so no long-lived secret ever has to be on this machine.
    if os.environ.get("GDRIVE_ACCESS_TOKEN"):
        return os.environ["GDRIVE_ACCESS_TOKEN"]
    if _tok["value"] and time.time() - _tok["at"] < 45 * 60:
        return _tok["value"]
    body = urllib.parse.urlencode({
        "client_id": os.environ["GDRIVE_CLIENT_ID"], "client_secret": os.environ["GDRIVE_CLIENT_SECRET"],
        "refresh_token": os.environ["GDRIVE_REFRESH_TOKEN"], "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=body)) as r:
        _tok["value"], _tok["at"] = json.load(r)["access_token"], time.time()
    return _tok["value"]


def call(method, url, body=None, headers=None, raw=False):
    for attempt in range(5):
        h = {"Authorization": f"Bearer {token()}", **(headers or {})}
        data = json.dumps(body).encode() if isinstance(body, (dict, list)) else body
        if isinstance(body, (dict, list)):
            h["Content-Type"] = "application/json; charset=UTF-8"
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, data=data, method=method, headers=h))
            if raw:
                return r  # caller reads (and the GC closes) the stream
            with r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 308 and raw:
                return e
            if e.code in (429, 500, 502, 503, 504) and attempt < 4:
                time.sleep(2 ** (attempt + 1))
                continue
            raise RuntimeError(f"Drive {method} {url.split('?')[0]} -> {e.code}: {e.read()[:300]!r}") from None


def children(parent, folders_only=False):
    q = f"'{parent}' in parents and trashed=false" + (f" and mimeType='{FOLDER}'" if folders_only else "")
    out, page = [], None
    while True:
        params = {"q": q, "fields": "nextPageToken,files(id,name,mimeType,size)", "pageSize": "200"}
        if page:
            params["pageToken"] = page
        d = call("GET", f"{DRIVE}/files?{urllib.parse.urlencode(params)}")
        out += d.get("files", [])
        page = d.get("nextPageToken")
        if not page:
            return out


def ensure_folder(name, parent):
    for f in children(parent, folders_only=True):
        if f["name"] == name:
            return f["id"]
    return call("POST", f"{DRIVE}/files?fields=id", {"name": name, "mimeType": FOLDER, "parents": [parent]})["id"]


def download(file_id, path):
    r = call("GET", f"{DRIVE}/files/{file_id}?alt=media", raw=True)
    with open(path, "wb") as fh:
        while True:
            buf = r.read(1 << 20)
            if not buf:
                break
            fh.write(buf)


def upload(path, parent):
    size = os.path.getsize(path)
    name = os.path.basename(path)
    mime = {"mp4": "video/mp4", "json": "application/json", "csv": "text/csv", "webm": "video/webm",
            "png": "image/png", "jpg": "image/jpeg", "txt": "text/plain"}.get(name.rsplit(".", 1)[-1].lower(), "application/octet-stream")
    r = call("POST", f"{UPLOAD}/files?uploadType=resumable&fields=id,name,webViewLink", {"name": name, "parents": [parent]},
             headers={"X-Upload-Content-Type": mime, "X-Upload-Content-Length": str(size)}, raw=True)
    session = r.headers["Location"]
    if size == 0:
        return call("PUT", session, b"", headers={"Content-Length": "0"})
    with open(path, "rb") as fh:
        offset = 0
        while offset < size:
            chunk = fh.read(CHUNK)
            end = offset + len(chunk) - 1
            res = call("PUT", session, chunk, headers={"Content-Range": f"bytes {offset}-{end}/{size}"}, raw=True)
            if res.status in (200, 201):
                return json.load(res)
            got = res.headers.get("Range")  # Drive may keep fewer bytes than sent; resume from what it has
            offset = int(got.split("-")[1]) + 1 if got else 0
            fh.seek(offset)
    raise RuntimeError(f"upload of {name} ended without a file id")


def pull(shoot_id, dest):
    os.makedirs(dest, exist_ok=True)
    raw = next((f["id"] for f in children(shoot_id, True) if f["name"] == "raw"), None)
    if not raw:
        raise SystemExit(f"no raw/ folder in {shoot_id}")
    got = []
    for f in children(raw):
        if f["mimeType"] == FOLDER:
            continue
        path = os.path.join(dest, f["name"])
        download(f["id"], path)
        got.append({"id": f["id"], "name": f["name"], "path": path, "size": os.path.getsize(path)})
    print(json.dumps(got, indent=1))


def push(src, shoot_id, into="cuts"):
    top = ensure_folder(into, shoot_id)
    ids, out = {"": top}, []
    for root, dirs, files in os.walk(src):
        dirs.sort()
        rel = os.path.relpath(root, src)
        rel = "" if rel == "." else rel
        if rel not in ids:
            parent = ids[os.path.dirname(rel)]
            ids[rel] = ensure_folder(os.path.basename(rel), parent)
        for name in sorted(files):
            meta = upload(os.path.join(root, name), ids[rel])
            out.append({"path": os.path.join(rel, name), "id": meta.get("id"), "link": meta.get("webViewLink", "")})
    print(json.dumps({"folder_id": top, "folder_url": f"https://drive.google.com/drive/folders/{top}", "files": out}, indent=1))


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 3 and a[0] == "pull":
        pull(a[1], a[2])
    elif len(a) >= 3 and a[0] == "push":
        push(a[1], a[2], a[a.index("--into") + 1] if "--into" in a else "cuts")
    else:
        sys.exit(__doc__)

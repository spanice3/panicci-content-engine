#!/usr/bin/env python3
"""Find Sammy's face so nothing gets drawn on it.

YuNet (OpenCV Zoo, MIT, 230 KB) run through onnxruntime, which faster-whisper already installs: no new
dependency, no environment rebuild. Two calls matter:

  track(mp4)          -> {"w","h","samples":[(t, (x0,y0,x1,y1)), ...]} largest face every 0.5 s, source pixels
  detect_image(path)  -> (x0,y0,x1,y1) of the largest face in a still, or None

If onnxruntime or the model is missing, both return empty and callers fall back to their old placement."""
import json, os, subprocess
import numpy as np

MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "face_detection_yunet_2023mar.onnx")
N = 640
_SESS = None


def _session():
    global _SESS
    if _SESS is None:
        import onnxruntime as ort
        o = ort.SessionOptions(); o.intra_op_num_threads = 2; o.inter_op_num_threads = 1
        _SESS = ort.InferenceSession(MODEL, o, providers=["CPUExecutionProvider"])
    return _SESS


def _faces(bgr640, score_min=0.6):
    """bgr640: (640,640,3) uint8, BGR. Returns [(score, x0, y0, x1, y1)] in that 640 frame, NMS'd."""
    blob = bgr640.astype(np.float32).transpose(2, 0, 1)[None]
    out = dict(zip([o.name for o in _session().get_outputs()], _session().run(None, {"input": blob})))
    found = []
    for s in (8, 16, 32):
        g = N // s
        cls = np.clip(out[f"cls_{s}"][0, :, 0], 0, 1); obj = np.clip(out[f"obj_{s}"][0, :, 0], 0, 1)
        score = np.sqrt(cls * obj); idx = np.where(score >= score_min)[0]
        if not len(idx):
            continue
        bb = out[f"bbox_{s}"][0, idx]; r, c = idx // g, idx % g
        cx, cy = (c + bb[:, 0]) * s, (r + bb[:, 1]) * s
        w, h = np.exp(bb[:, 2]) * s, np.exp(bb[:, 3]) * s
        found += [(float(sc), float(x - ww / 2), float(y - hh / 2), float(x + ww / 2), float(y + hh / 2))
                  for sc, x, y, ww, hh in zip(score[idx], cx, cy, w, h)]
    found.sort(reverse=True); keep = []
    for f in found:                                   # plain NMS, IoU 0.3
        if all(_iou(f[1:], k[1:]) < 0.3 for k in keep):
            keep.append(f)
    return keep


def _iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy; u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u > 0 else 0


def _largest(faces, scale):
    if not faces:
        return None
    f = max(faces, key=lambda f: (f[3] - f[1]) * (f[4] - f[2]))
    return tuple(round(v / scale, 1) for v in f[1:])


def _probe(mp4):
    w, h = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                    "stream=width,height", "-of", "csv=p=0", mp4]).decode().split(",")[:2]
    return int(w), int(h)


def track(mp4, every=0.5, cache=True):
    """Largest face every `every` seconds, in source pixels. Cached beside the clip (<mp4>.faces.json)."""
    cpath = os.path.join(os.path.dirname(os.path.abspath(mp4)), "." + os.path.basename(mp4) + ".faces.json")  # dot-file: never pushed
    if cache and os.path.exists(cpath) and os.path.getmtime(cpath) >= os.path.getmtime(mp4):
        j = json.load(open(cpath)); j["samples"] = [(t, tuple(b)) for t, b in j["samples"]]
        return j
    W, H = _probe(mp4)
    res = {"w": W, "h": H, "samples": []}
    try:
        _session()
    except Exception as e:                            # no onnxruntime / no model: callers fall back
        res["error"] = str(e)[:200]
        return res
    sc = N / max(W, H); sw, sh = round(W * sc) // 2 * 2, round(H * sc) // 2 * 2
    p = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", mp4, "-vf",
                          f"fps=1/{every},scale={sw}:{sh},pad={N}:{N}:0:0", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         stdout=subprocess.PIPE)
    n, fb = 0, N * N * 3
    while True:
        buf = p.stdout.read(fb)
        if len(buf) < fb:
            break
        box = _largest(_faces(np.frombuffer(buf, np.uint8).reshape(N, N, 3)), sc)
        if box:
            res["samples"].append((round(n * every + every / 2, 2), box))
        n += 1
    p.wait()
    res["samples"] = _clean(res["samples"])
    if cache:
        json.dump(res, open(cpath, "w"))
    return res


def _clean(samples):
    """Drop stray hits (a poster face, a reflection): keep boxes near the median face in size and place."""
    if len(samples) < 3:
        return samples
    b = np.array([s[1] for s in samples]); w = b[:, 2] - b[:, 0]; cx = (b[:, 0] + b[:, 2]) / 2; cy = (b[:, 1] + b[:, 3]) / 2
    mw, mx, my = np.median(w), np.median(cx), np.median(cy)
    ok = (w > mw * 0.6) & (w < mw * 1.6) & (abs(cx - mx) < mw * 2.5) & (abs(cy - my) < mw * 2.5)
    return [s for s, k in zip(samples, ok) if k]


def detect_image(path):
    from PIL import Image
    im = Image.open(path).convert("RGB"); W, H = im.size; sc = N / max(W, H)
    small = im.resize((round(W * sc), round(H * sc)))
    canvas = Image.new("RGB", (N, N)); canvas.paste(small, (0, 0))
    arr = np.asarray(canvas)[:, :, ::-1].copy()
    return _largest(_faces(arr), sc)


def zone(box, top=0.25, bottom=0.12, side=0.10):
    """Face box -> the area nothing may cover: forehead/cap above it, chin and beard below, ears beside."""
    x0, y0, x1, y1 = box; w, h = x1 - x0, y1 - y0
    return (x0 - w * side, y0 - h * top, x1 + w * side, y1 + h * bottom)


if __name__ == "__main__":
    import sys
    for f in sys.argv[1:]:
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            print(f, detect_image(f))
        else:
            r = track(f, cache=False)
            print(f, r["w"], r["h"], len(r["samples"]), "faces", r["samples"][:3], r.get("error", ""))

#!/usr/bin/env python3
"""Cut every studio take in a folder, two at a time, and print one JSON summary. The Clipper's STEP 3 in one call.

  python3 clip_batch.py <raw_dir> <cuts_dir> [--jobs 2] [--dry-run]

Each <take>.mp4 in raw_dir needs its Script data <take>.json beside it (the studio uploads both).
  - 50-5-3 takes ("adsShoot": true): adbuild.py --render test --brand 9x16 (round 1 hook test + every module).
    Ready sets (adsSet.meatsScripted) build their own ad matrix; other shoots ask the studio (needs STUDIO_API_KEY).
  - every other take: run.py with the take's own script for exact captions, 9x16 + 1x1.
Cuts land in cuts_dir/<take>/, logs in cuts_dir/../logs/<take>.log (kept out of the Drive push).
A take that fails doesn't stop the others. Exit code 0 when at least one take was cut, 1 when none were.
"""
import argparse, concurrent.futures as cf, csv, glob, json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))


def plan(raw, cuts, logs):
    jobs = []
    for mp4 in sorted(glob.glob(os.path.join(raw, "*.mp4"))):
        base = os.path.splitext(os.path.basename(mp4))[0]
        meta = os.path.join(raw, base + ".json")
        if not os.path.exists(meta):
            jobs.append(dict(take=base, skip="no Script data .json beside the video"))
            continue
        m = json.load(open(meta))
        out = os.path.join(cuts, base)
        if m.get("adsShoot"):
            cmd = [sys.executable, "adbuild.py", mp4, "--meta", meta, "--render", "test", "--brand", "9x16",
                   "--out-dir", out]
            kind = "50-5-3"
        else:
            cmd = [sys.executable, "run.py", mp4, "--formats", "9x16,1x1", "--out-dir", out]
            script = "\n".join(l for l in (m.get("script") or "").splitlines() if l.strip() != "|").strip()
            if script:
                sp = os.path.join(logs, base + ".script.txt")
                open(sp, "w").write(script)
                cmd[3:3] = ["--script", sp]
            kind = "talking-head"
        jobs.append(dict(take=base, kind=kind, cmd=cmd, out=out, log=os.path.join(logs, base + ".log"),
                         ready=(m.get("readyScript") or {}).get("id") or (m.get("adsSet") or {}).get("id")))
    return jobs


def run(job):
    t0 = time.time()
    with open(job["log"], "w") as fh:
        rc = subprocess.call(job["cmd"], cwd=HERE, stdout=fh, stderr=subprocess.STDOUT)
    res = dict(take=job["take"], kind=job["kind"], ok=rc == 0, seconds=round(time.time() - t0))
    if rc != 0:
        tail = [l.strip() for l in open(job["log"], errors="replace") if l.strip()]
        res["error"] = tail[-1][:300] if tail else f"exit {rc}"
        return res
    for scratch in glob.glob(os.path.join(job["out"], ".*")):          # .kit_9x16/ etc: render scratch, not cuts
        shutil.rmtree(scratch, ignore_errors=True) if os.path.isdir(scratch) else os.remove(scratch)
    files = sorted(os.path.relpath(p, job["out"]) for p in glob.glob(os.path.join(job["out"], "**", "*.mp4"),
                                                                       recursive=True))
    res["videos"] = len(files)
    if job["kind"] == "50-5-3":
        man = os.path.join(job["out"], "manifest.csv")
        res["ads"] = sum(1 for _ in csv.DictReader(open(man))) if os.path.exists(man) else 0
        res["modules"] = len(glob.glob(os.path.join(job["out"], "modules", "*.mp4")))
        mx = os.path.join(job["out"], "ad-matrix.snapped.json")
        if os.path.exists(mx):
            j = json.load(open(mx))
            res["reshoot"] = [r.get("reason", "") for r in j.get("reshoot", [])]
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("raw"); ap.add_argument("cuts")
    ap.add_argument("--jobs", type=int, default=2); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    logs = os.path.join(os.path.dirname(os.path.abspath(a.cuts)), "logs")
    os.makedirs(a.cuts, exist_ok=True); os.makedirs(logs, exist_ok=True)
    jobs = plan(a.raw, a.cuts, logs)
    todo = [j for j in jobs if "cmd" in j]
    if a.dry_run:
        print(json.dumps([dict(take=j["take"], kind=j.get("kind"), cmd=" ".join(j.get("cmd", [])) or j.get("skip"))
                          for j in jobs], indent=2))
        sys.exit(0)
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=max(1, a.jobs)) as ex:
        results = list(ex.map(run, todo))
    results += [dict(take=j["take"], ok=False, error=j["skip"]) for j in jobs if "skip" in j]
    out = dict(seconds=round(time.time() - t0), cut=sum(r["ok"] for r in results),
               failed=sum(not r["ok"] for r in results), takes=results)
    print(json.dumps(out, indent=2))
    sys.exit(0 if out["cut"] else 1)

#!/usr/bin/env python3
"""Execute rea-video remake jobs with capsule-cinema's video generation tools.

Runs inside capsule-cinema's Python environment (its .env provides API keys).
Writes results.json next to jobs.json; rea-video `assemble` consumes it."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path


def _video_path(res) -> str | None:
    """Find the generated file in the various result shapes capsule-cinema tools return."""
    if isinstance(res, str):
        return res if res.lower().endswith((".mp4", ".mov", ".webm")) and Path(res).is_file() else None
    if not isinstance(res, dict):
        return None
    for key in ("output_path", "video_path", "local_path", "path", "file_path"):
        v = res.get(key)
        if isinstance(v, str) and Path(v).is_file():
            return v
    for key in ("result", "data", "video"):
        v = _video_path(res.get(key)) if res.get(key) is not None else None
        if v:
            return v
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--only", default="", help="comma-separated shots: 3,5 or shot_003,shot_005")
    ap.add_argument("--capsule-root", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    jobs_path = Path(args.jobs).expanduser().resolve()
    spec = json.loads(jobs_path.read_text(encoding="utf-8"))
    only = set()
    for x in args.only.split(","):
        x = x.strip()
        if not x:
            continue
        m = re.fullmatch(r"(?:shot_?)?0*(\d+)", x, re.I)
        if not m:
            sys.exit(f"--only 看不懂 {x!r}：写镜头序号（3）或镜头 id（shot_003），逗号分隔")
        only.add(int(m.group(1)))
    results_path = jobs_path.with_name("results.json")
    results = json.loads(results_path.read_text(encoding="utf-8")) if results_path.is_file() else {"results": {}}

    root = Path(args.capsule_root).expanduser().resolve()
    planned = Path(spec.get("capsule_root") or "").expanduser().resolve()
    if planned != root:
        sys.exit(f"jobs.json 的 capsule_root（{planned}）与 --capsule-root（{root}）不一致；确认来源可信后用 --capsule-root 指定")
    out_root = root / "output"
    for j in spec["jobs"]:
        od = Path(j.get("params", {}).get("output_dir", "")).expanduser().resolve()
        if j.get("executor") == "capsule_cinema" and not od.is_relative_to(out_root):
            sys.exit(f"shot {j.get('shot')}: output_dir 不在 {out_root} 下，拒绝执行")

    todo = [j for j in spec["jobs"] if j["executor"] == "capsule_cinema" and (not only or j["shot"] in only)]
    if only and not todo:
        have = sorted(j["shot"] for j in spec["jobs"] if j["executor"] == "capsule_cinema")
        sys.exit(f"--only {args.only} 里没有需要生成的镜头；可生成的镜头序号：{have}")
    print(f"{len(todo)} generation job(s); run dir {spec['run_dir']}")
    if args.dry_run:
        for j in todo:
            p = dict(j["params"])
            p["prompt"] = p["prompt"][:120] + ("…" if len(p["prompt"]) > 120 else "")
            print(json.dumps({"shot": j["shot"], "label": j["label"], **p}, ensure_ascii=False))
        return

    sys.path.insert(0, str(root / "lib"))
    sys.path.insert(0, str(root / "scripts"))
    from env_loader import load_video_agent_env  # noqa: E402

    load_video_agent_env(root)
    from custom_tools.video_generation.video_generation_tool import UniversalVideoGenerationTool  # noqa: E402

    tool = UniversalVideoGenerationTool()
    failed = []
    for j in todo:
        Path(j["params"]["output_dir"]).mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        print(f"shot {j['shot']}: {j['params']['generation_type']} via {j['params']['engine']} ...", flush=True)
        try:
            res = tool._run(**j["params"])
        except Exception as exc:  # keep going, record the failure
            res = {"error": str(exc)}
        video = _video_path(res)
        results["results"][str(j["shot"])] = {"id": j["id"], "video": video, "raw": res if not video else None,
                                              "seconds": round(time.time() - t0, 1), "trim_to": j["trim_to"]}
        results_path.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"  -> {video or res}", flush=True)
        if not video:
            failed.append(str(j["shot"]))
    print(f"results: {results_path}")
    if failed:
        sys.exit(f"{len(failed)}/{len(todo)} 个镜头没生成出视频：{', '.join(failed)}（详情见 results.json）")


if __name__ == "__main__":
    main()

"""rea-video command line."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .util import LOG, OCR_LANGS, load_env_files, read_json, setup_logging
from .classify import LABELS
from .vlm import vlm_note

DEFAULT_CAPSULE_ROOT = os.getenv("CAPSULE_CINEMA_ROOT", str(Path.home() / "code/github/capsule-cinema"))


def _env(args) -> None:
    from .memory import pref

    files = [Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"]
    env_file = getattr(args, "env_file", None) or pref("env_file")
    if env_file:
        files.insert(0, Path(env_file))
    loaded = load_env_files(files)
    if loaded:
        LOG.debug("env loaded from %s", loaded)


def _ocr_lang(args) -> None:
    """--ocr-lang (or prefs ocr_lang) -> $REA_OCR_LANG, which overlay.get_ocr reads."""
    from .memory import pref

    lang = getattr(args, "ocr_lang", None) or pref("ocr_lang")
    if lang:
        if lang not in OCR_LANGS:
            raise SystemExit(f"错误：不支持的 OCR 语言 {lang}（可选：{', '.join(OCR_LANGS)}）")
        os.environ["REA_OCR_LANG"] = lang


def cmd_decompose(args) -> int:
    from .pipeline import decompose

    _ocr_lang(args)

    out = Path(args.out) if args.out else Path("out") / Path(args.video).stem
    from .memory import pref

    meta = read_json(Path(args.meta)) if args.meta else None
    use_vlm = args.vlm or (pref("vlm") == "on" and not args.no_vlm)
    stems = not args.no_stems and pref("stems", "on") == "on"
    b = decompose(args.video, out, use_vlm=use_vlm, whole_vlm=not args.no_whole, ocr=not args.no_ocr,
                  workers=args.workers, engine=args.engine or pref("engine", "seedance2.0"), platform_meta=meta, stems=stems,
                  packaging=not args.no_packaging)
    print(json.dumps({"out": str(out), "verdict": b["summary"]["verdict"], "shots": b["summary"]["shots"],
                      "confidence": b["summary"]["confidence"], "vlm": b["summary"]["vlm"],
                      "report": str(out / "report.html")}, ensure_ascii=False, indent=2))
    return 0


def cmd_review(args) -> int:
    """Write review_tasks.json + review_answers.json so a multimodal agent can act as the VLM."""
    from .review import build_tasks

    out = Path(args.out_dir)
    b = read_json(out / "breakdown.json")
    tasks, answers = build_tasks(b, str(out))
    (out / "review_tasks.json").write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
    ans_path = out / "review_answers.json"
    if args.force or not ans_path.is_file():
        ans_path.write_text(json.dumps(answers, ensure_ascii=False, indent=2), encoding="utf-8")
    high = [s for s in tasks["shots"] if s["priority"] == "high"]
    print(f"{len(tasks['shots'])} 个镜头待看图复核，其中 {len(high)} 个优先：" + ", ".join(f"{s['id']}({'; '.join(s['why'])})" for s in high))
    print(f"说明和图片路径：{out / 'review_tasks.json'}")
    print(f"把答案填进：{ans_path}")
    print(f"然后运行：rea-video apply-review {out} --by <你的名字>")
    return 0


def cmd_apply_review(args) -> int:
    from .pipeline import finalize
    from .review import apply_answers

    out = Path(args.out_dir)
    b = read_json(out / "breakdown.json")
    answers = read_json(Path(args.answers) if args.answers else out / "review_answers.json")
    from .memory import pref

    log = apply_answers(b, answers, by=args.by or pref("reviewer"))
    b = finalize(b, out)
    for p in log["problems"]:
        print(f"跳过 {p}")
    changed = [(r["id"], log["before"][r["id"]], r["base"]["label"]) for r in b["shots"]
               if r["id"] in log["before"] and log["before"][r["id"]] != r["base"]["label"]]
    print(f"已并入 {len(log['applied'])}/{len(b['shots'])} 个镜头；改判 {len(changed)} 个" +
          ("：" + ", ".join(f"{i} {a}→{c}" for i, a, c in changed) if changed else ""))
    print(f"结论: {b['summary']['verdict']}")
    print(f"VLM: {b['summary']['vlm']}")
    return 0 if log["applied"] else 1


def cmd_stems(args) -> int:
    from .stems import extract_stems

    out = Path(args.out) if args.out else Path("out") / Path(args.video).stem
    print(json.dumps(extract_stems(args.video, out), ensure_ascii=False, indent=2))
    return 0


def cmd_probe(args) -> int:
    from .media import video_info
    from .probe import provenance

    info = video_info(args.video)
    p = provenance(info)
    p.pop("tags", None) if not args.tags else None
    print(json.dumps({"width": info.width, "height": info.height, "fps": info.fps, "duration": info.duration,
                      "vcodec": info.vcodec, "aspect_ratio": info.aspect_ratio, "provenance": p}, ensure_ascii=False, indent=2))
    return 0


def cmd_eval(args) -> int:
    from .evaluate import evaluate

    _ocr_lang(args)

    res = evaluate(Path(args.labels), Path(args.out), use_vlm=args.vlm, ocr=not args.no_ocr, reuse=not args.fresh,
                   only=set(args.only.split(",")) if args.only else None, stems=args.stems)
    print(json.dumps(res["summary"], ensure_ascii=False, indent=2))
    return 0


def cmd_capsule(args) -> int:
    from .integrations.capsule_cinema import export_capsule_analysis

    b = read_json(Path(args.breakdown))
    out = export_capsule_analysis(b, Path(args.out) if args.out else Path(args.breakdown).with_name("capsule_analysis.json"))
    print(out)
    return 0


def cmd_remake_plan(args) -> int:
    from .integrations.capsule_cinema import build_remake_jobs

    bdir = Path(args.breakdown).parent
    from .memory import pref

    jobs = build_remake_jobs(read_json(Path(args.breakdown)), bdir, capsule_root=Path(args.capsule_root),
                             engine=args.engine or pref("engine", "seedance2.0"),
                             mode=args.mode, labels=args.labels.split(",") if args.labels else None)
    print(jobs)
    return 0


def _capsule_python(explicit: str | None, capsule_root: Path) -> str:
    """capsule-cinema 的解释器：--python > $CAPSULE_CINEMA_PYTHON > <capsule-root>/.venv/bin/python > 当前解释器。"""
    if explicit or os.getenv("CAPSULE_CINEMA_PYTHON"):
        return explicit or os.environ["CAPSULE_CINEMA_PYTHON"]
    venv = capsule_root.expanduser() / ".venv/bin/python"
    return str(venv) if venv.is_file() else sys.executable


def _run_integration(script: str, python: str, argv: list[str]) -> int:
    import subprocess

    path = Path(__file__).resolve().parent / "integrations" / script
    return subprocess.call([python, str(path), *argv])


def cmd_remake_run(args) -> int:
    jobs = Path(args.jobs).expanduser().resolve()
    root = Path(read_json(jobs).get("capsule_root") or DEFAULT_CAPSULE_ROOT)
    argv = ["--jobs", str(jobs)] + (["--only", args.only] if args.only else []) + (["--dry-run"] if args.dry_run else [])
    # 试跑不调用 capsule-cinema，用当前解释器即可
    python = sys.executable if args.dry_run and not args.python else _capsule_python(args.python, root)
    return _run_integration("run_remake.py", python, argv)


def cmd_capsule_draft(args) -> int:
    argv = ["--breakdown", str(Path(args.breakdown).expanduser().resolve()), "--capsule-root", args.capsule_root]
    argv += ["--capsule-name", args.capsule_name] if args.capsule_name else []
    argv += ["--capsule-display-name", args.capsule_display_name] if args.capsule_display_name else []
    argv += ["--write-capsule"] if args.write_capsule else []
    argv += ["--overwrite-capsule"] if args.overwrite_capsule else []
    return _run_integration("to_capsule.py", _capsule_python(args.python, Path(args.capsule_root)), argv)


def cmd_assemble(args) -> int:
    from .remake import assemble

    print(assemble(Path(args.breakdown), Path(args.results), Path(args.out) if args.out else None))
    return 0


def cmd_tiles(args) -> int:
    """Time-labelled frame grid for close inspection of a passage."""
    import cv2
    import numpy as np

    from .media import extract_frame, video_info
    from .visual import shot_sheet

    info = video_info(args.video)
    end = args.end if args.end is not None else info.duration
    times = list(np.arange(args.start, end, args.every))[: args.max]
    import tempfile

    frames = []
    with tempfile.TemporaryDirectory() as tmpd:
        for i, t in enumerate(times):
            p = extract_frame(args.video, float(t), Path(tmpd) / f"tile_{i:03d}.jpg", width=args.cell)
            img = cv2.imread(str(p))
            if img is not None:
                frames.append(img)
    rows = [frames[i:i + args.cols] for i in range(0, len(frames), args.cols)]
    paths = []
    for r, row in enumerate(rows):
        out = Path(args.out) if len(rows) == 1 else Path(args.out).with_name(f"{Path(args.out).stem}_{r + 1}{Path(args.out).suffix}")
        shot_sheet(row, [float(t) for t in times[r * args.cols:(r + 1) * args.cols]], out, n=len(row), cell_w=args.cell)
        paths.append(str(out))
    print(json.dumps({"tiles": paths, "times": [round(float(t), 3) for t in times]}, ensure_ascii=False))
    return 0


def cmd_summary(args) -> int:
    """Compact, agent-friendly view of a breakdown (instead of reading the whole JSON)."""
    b = read_json(Path(args.breakdown))
    s = b["summary"]
    lines = [f"{b['source']['filename']} | {b['source']['duration']}s {b['source']['width']}x{b['source']['height']} {b['source']['fps']}fps",
             f"结论: {s['verdict']}", f"置信度: {s['confidence']}", f"VLM: {s.get('vlm') or vlm_note(b['analysis']['vlm'])}", ""]
    vc = b.get("video_context") or {}
    if vc.get("transcoded"):
        lines.append(f"平台转码: {'、'.join(vc.get('platform', []))}（噪声类证据失效；原生 30fps 无重复帧: {vc.get('native30')}）")
    prov = b.get("provenance", {})
    if prov.get("aigc") or prov.get("hints"):
        lines.append(f"元数据: aigc={prov.get('aigc')} hints={prov.get('hints')}")
    from .aspects import shot_text
    from .memory import hint_for, patterns

    pats = patterns()
    for r in b["shots"]:
        base = r["base"]
        alt = sorted(base["probs"].items(), key=lambda kv: -kv[1])[1]
        det = r["deterministic"]["probs"]
        past = None if base["decided_by"] == "user" else hint_for(max(det, key=det.get), pats)
        mat = (r.get("material") or {}).get("origin_zh", "")
        second = "(用户纠正)" if base["decided_by"] == "user" else f"(次选 {alt[0]} {alt[1]:.2f})"
        lines.append(f"#{r['index']:>2} {r['start']:7.2f}-{r['end']:7.2f} {base['label']:<14} {base['confidence']:.2f} {second} "
                     f"| 素材:{mat} | 叠加:{','.join(sorted({l['kind'] for l in r.get('layers', [])})) or '-'} | {r['features'].get('camera')}"
                     + ("  ← 低置信，需要复核" if base["confidence"] < 0.6 else "")
                     + (f"  ← {base['uncertain']}" if base.get("uncertain") else "")
                     + (f"  ← 有分歧：{base['disputed']}" if base.get("disputed") else "")
                     + ("  ← 用户纠正过素材来源" if (r.get("material") or {}).get("user_corrected") else "")
                     + (f"  ← {past}" if past else "")
                     + (f" | {shot_text(r)}" if r["base"]["label"] in ("live_action", "avatar") and shot_text(r) else ""))
    if s.get("aspects"):
        lines += [""] + s["aspects"]
    a = b.get("audio", {})
    if a.get("has_audio"):
        mu = a.get("music", {})
        lines += ["", f"人声: {a.get('voice', {}).get('present')} ({a.get('voice', {}).get('ratio')}) | 音乐: {mu.get('present')} "
                      f"{mu.get('tempo_bpm')}BPM {(mu.get('key') or {}).get('tonic', '')}{(mu.get('key') or {}).get('mode', '')} | "
                      f"音效: {len((b.get('audio_plan') or {}).get('sfx_merged', []))} | 卡点: {a.get('beat_synced_edit')}"]
        if (b.get("sound_sources") or {}).get("summary_zh"):
            lines.append("声音来源: " + b["sound_sources"]["summary_zh"])
        if (b.get("stems") or {}).get("ok"):
            lines.append("音轨: stems/original.wav（原声） stems/vocals.wav（人声） stems/music.wav（配乐）")
    pk = b.get("packaging")
    if pk:
        lines += [""] + [f"包装: {x}" for x in (pk.get("summary_zh") or ["没有检出后期叠加的文字或贴纸"])]
        low = [st for st in pk.get("stickers", []) if not st.get("in_picture") and st.get("confidence") in ("low", "vlm")]
        if low:
            lines.append("包装: 需要看图确认的贴纸 " + "、".join(f"{st['id']} {st['t0']:.1f}-{st['t1']:.1f}s" for st in low)
                         + "（截图在 packaging/）")
        if pk.get("files"):
            lines.append("包装文件: " + " ".join(pk["files"].values()))
    print("\n".join(lines))
    return 0


def cmd_correct(args) -> int:
    """The user says a shot is wrong: fix this breakdown and remember the correction."""
    from .memory import correct
    from .pipeline import finalize

    out = Path(args.out_dir)
    b = read_json(out / "breakdown.json")
    real = None if args.real is None else args.real == "yes"
    try:
        logged = correct(b, label=args.label, real=real, shots=args.shots, start=args.start, end=args.end, note=args.note or "")
    except ValueError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    b = finalize(b, out)
    changed = [f"{c['shot']} {c['before']}→{c['label']}" for c in logged if c.get("label") and c["before"] != c["label"]]
    print(f"已纠正 {len(logged)} 个镜头" + (("：" + ", ".join(changed)) if changed else "") + "，并记入记忆")
    print(f"结论: {b['summary']['verdict']}")
    return 0


def cmd_prefs(args) -> int:
    from .memory import PREF_KEYS, add_note, load_prefs, remove_note, set_pref

    try:
        if args.note:
            add_note(args.note)
        elif args.remove_note:
            remove_note(args.remove_note)
        elif args.key and args.unset:
            set_pref(args.key, None)
        elif args.key and args.value is not None:
            set_pref(args.key, args.value)
        elif args.key:
            print(load_prefs().get(args.key, ""))
            return 0
    except ValueError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    prefs = load_prefs()
    for k, desc in PREF_KEYS.items():
        print(f"{k:<9} = {prefs.get(k, '（未设置）')}    # {desc}")
    for i, n in enumerate(prefs.get("notes", []), 1):
        print(f"说明 {i}: {n}")
    return 0


def cmd_memory(args) -> int:
    from .memory import export_labels, summary_lines

    if args.export_labels:
        n = export_labels(Path(args.export_labels))
        print(f"已导出 {n} 条视频的纠正到 {args.export_labels}（先把 path 填好，再用 rea-video eval 评测）")
        return 0
    print("\n".join(summary_lines()))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="rea-video", description="逆向拆解视频：逐镜头判断实拍 / AI 生成 / 代码渲染 / 混合，并生成复刻方案")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--env-file", help="额外的 .env（例如 capsule-cinema/.env，用于 VLM 配置）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("decompose", help="拆解一条视频")
    d.add_argument("video")
    d.add_argument("-o", "--out")
    d.add_argument("--vlm", action="store_true", help="启用多模态大模型（VLM）看画面逐镜判断；建议开，不开也能跑，只是实拍/AI/3D 的区分更弱")
    d.add_argument("--no-vlm", action="store_true", help="本次不开 VLM（覆盖 prefs 里的 vlm=on）")
    d.add_argument("--no-whole", action="store_true", help="跳过整片结构/文案 VLM 分析")
    d.add_argument("--no-ocr", action="store_true", help="不做 OCR（字幕/花字时间轴也会跳过，只剩贴纸检测）")
    d.add_argument("--ocr-lang", choices=OCR_LANGS, help="字幕/花字的语言：zh 中英（默认）、ja 日文（首次使用自动下载识别模型）；也可用 prefs ocr_lang 设成默认")
    d.add_argument("--no-packaging", action="store_true", help="跳过剪辑包装层（整片字幕时间轴、花字、贴纸/动图、音效卡点）；省掉约每分钟 30–50 秒")
    d.add_argument("--workers", type=int, default=3)
    d.add_argument("--engine", help="复刻计划使用的 capsule-cinema 视频引擎（默认 prefs 里的 engine，否则 seedance2.0）")
    d.add_argument("--meta", help='平台元数据 JSON，例如 {"music": {"title": "xx", "author": "yy", "is_original": false, "popular": true}}')
    d.add_argument("--no-stems", action="store_true", help="不做人声/配乐分离（默认会输出 stems/original.wav、vocals.wav、music.wav）")
    d.set_defaults(func=cmd_decompose)

    st = sub.add_parser("stems", help="只把声音剥离成 原声 / 人声 / 配乐 三条轨")
    st.add_argument("video")
    st.add_argument("-o", "--out")
    st.set_defaults(func=cmd_stems)

    p = sub.add_parser("probe", help="只看容器元数据/来源线索")
    p.add_argument("video")
    p.add_argument("--tags", action="store_true")
    p.set_defaults(func=cmd_probe)

    e = sub.add_parser("eval", help="在带标注的样本集上评测拆解准确率")
    e.add_argument("labels", help="labels.yaml")
    e.add_argument("-o", "--out", default="out/eval")
    e.add_argument("--vlm", action="store_true")
    e.add_argument("--no-ocr", action="store_true")
    e.add_argument("--ocr-lang", choices=OCR_LANGS, help="同 decompose --ocr-lang")
    e.add_argument("--fresh", action="store_true", help="不复用已有拆解结果")
    e.add_argument("--only", default="", help="只重新拆解这些 id（逗号分隔），其余复用缓存并重新分类")
    e.add_argument("--stems", action="store_true", help="对带音频真值的样本做人声分离，并在干声上重测唱/说")
    e.set_defaults(func=cmd_eval)

    c = sub.add_parser("capsule", help="导出 capsule-cinema 的视频分析 JSON（供生成胶囊草稿）")
    c.add_argument("breakdown")
    c.add_argument("-o", "--out")
    c.set_defaults(func=cmd_capsule)

    r = sub.add_parser("remake-plan", help="为 AI 类镜头生成 capsule-cinema 复刻任务")
    r.add_argument("breakdown")
    r.add_argument("--capsule-root", default=DEFAULT_CAPSULE_ROOT)
    r.add_argument("--engine", help="默认 prefs 里的 engine，否则 seedance2.0")
    r.add_argument("--mode", default="first_last_frame", choices=["first_last_frame", "image_to_video", "text_to_video"])
    r.add_argument("--labels", default="", help="只复刻这些底层类别（逗号分隔），默认 ai_video,cg_3d,live_action,avatar")
    r.set_defaults(func=cmd_remake_plan)

    rr = sub.add_parser("remake-run", help="用 capsule-cinema 执行 remake-plan 生成的任务（会计费，先 --dry-run）")
    rr.add_argument("jobs", help="remake-plan 输出的 jobs.json")
    rr.add_argument("--dry-run", action="store_true", help="只列出任务和参数，不调用模型")
    rr.add_argument("--only", default="", help="只跑这些镜头（逗号分隔）")
    rr.add_argument("--python", help="capsule-cinema 的 Python；默认 $CAPSULE_CINEMA_PYTHON 或 <capsule-root>/.venv/bin/python")
    rr.set_defaults(func=cmd_remake_run)

    cd = sub.add_parser("capsule-draft", help="用拆解结果生成 capsule-cinema 胶囊草稿")
    cd.add_argument("breakdown")
    cd.add_argument("--capsule-root", default=DEFAULT_CAPSULE_ROOT)
    cd.add_argument("--capsule-name", default="")
    cd.add_argument("--capsule-display-name", default="")
    cd.add_argument("--write-capsule", action="store_true", help="落盘到 capsule-cinema 的 capsules/")
    cd.add_argument("--overwrite-capsule", action="store_true")
    cd.add_argument("--python", help="capsule-cinema 的 Python；默认同 remake-run")
    cd.set_defaults(func=cmd_capsule_draft)

    a = sub.add_parser("assemble", help="把复刻结果按原时间线拼回，并输出对比视频")
    a.add_argument("breakdown")
    a.add_argument("results", help="remake-run 输出的 results.json（或自己写的同格式文件）")
    a.add_argument("-o", "--out")
    a.set_defaults(func=cmd_assemble)

    t = sub.add_parser("tiles", help="按时间抽帧拼图，近距离检查某一段（agent 复核用）")
    t.add_argument("video")
    t.add_argument("--start", type=float, default=0.0)
    t.add_argument("--end", type=float)
    t.add_argument("--every", type=float, default=0.5)
    t.add_argument("--cols", type=int, default=6)
    t.add_argument("--cell", type=int, default=320)
    t.add_argument("--max", type=int, default=48)
    t.add_argument("-o", "--out", default="out/tiles.jpg")
    t.set_defaults(func=cmd_tiles)

    sm = sub.add_parser("summary", help="紧凑打印拆解结果（低置信镜头会被标出来）")
    sm.add_argument("breakdown")
    sm.set_defaults(func=cmd_summary)

    rv = sub.add_parser("review", help="能看图的 agent 当 VLM：生成逐镜看图任务和答案模板")
    rv.add_argument("out_dir", help="decompose 的输出目录")
    rv.add_argument("--force", action="store_true", help="覆盖已有的 review_answers.json")
    rv.set_defaults(func=cmd_review)

    ar = sub.add_parser("apply-review", help="把 agent 看图的答案并入结论，重写 breakdown.json 和报告")
    ar.add_argument("out_dir")
    ar.add_argument("answers", nargs="?", help="答案文件（默认 <out_dir>/review_answers.json）")
    ar.add_argument("--by", help="复核者名字（写进报告）")
    ar.set_defaults(func=cmd_apply_review)

    co = sub.add_parser("correct", help="用户指出判错：改正这条视频的结论，并记入记忆（以后同类镜头会提示复核）")
    co.add_argument("out_dir", help="decompose 的输出目录")
    co.add_argument("--shots", help="镜头编号，逗号分隔（如 3,5 或 shot_003），all 表示整条；也可用 --start/--end 指定时间段")
    co.add_argument("--start", type=float)
    co.add_argument("--end", type=float)
    co.add_argument("--label", help="正确的底层类别：" + "、".join(LABELS))
    co.add_argument("--real", choices=["yes", "no"], help="是否用了用户真实素材")
    co.add_argument("--note", help="用户的原话或理由，例如「这是定格动画，不是 AI」")
    co.set_defaults(func=cmd_correct)

    pf = sub.add_parser("prefs", help="查看 / 设置用户偏好（默认引擎、是否开 VLM、VLM 配置文件、复核者、自由文字说明）")
    pf.add_argument("key", nargs="?")
    pf.add_argument("value", nargs="?")
    pf.add_argument("--unset", action="store_true")
    pf.add_argument("--note", help="追加一条给 agent 看的偏好说明，例如「报告尽量短」")
    pf.add_argument("--remove-note", type=int, metavar="N")
    pf.set_defaults(func=cmd_prefs)

    me = sub.add_parser("memory", help="看记住了什么：偏好、常见纠正类型；可导出为评测样本")
    me.add_argument("--export-labels", metavar="YAML")
    me.set_defaults(func=cmd_memory)

    args = ap.parse_args(argv)
    setup_logging(args.verbose)
    _env(args)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

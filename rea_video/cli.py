"""rea-video command line."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .util import LOG, OCR_LANGS, load_env_files, read_json, setup_logging
from .i18n import LANGS, T, set_lang
from .classify import LABELS
from .vlm import vlm_note



def _env(args) -> None:
    from .memory import pref

    # 不读当前目录的 .env：在别人的仓库里运行时，它可以改 VLM 地址或 CAPSULE_CINEMA_PYTHON
    files = [Path(__file__).resolve().parent.parent / ".env"]
    explicit = getattr(args, "env_file", None)
    env_file = explicit or pref("env_file")
    if env_file:
        if not Path(env_file).expanduser().is_file():
            # silently skipping it made people think the VLM was configured
            msg = T("找不到配置文件 {p}", "env file not found: {p}", p=env_file)
            if explicit:
                raise SystemExit(f"rea-video: {msg}")
            LOG.warning("%s%s", msg, T("（来自 prefs env_file）", " (from prefs env_file)"))
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
    lang = args.lang or pref("lang", "zh")
    if lang not in LANGS:
        raise SystemExit(f"错误：不支持的报告语言 {lang}（可选：{', '.join(LANGS)}）")
    b = decompose(args.video, out, use_vlm=use_vlm, whole_vlm=not args.no_whole, ocr=not args.no_ocr,
                  workers=args.workers, engine=args.engine or pref("engine", "seedance2.0"), platform_meta=meta, stems=stems,
                  packaging=not args.no_packaging, lang=lang)
    print(json.dumps({"out": str(out), "verdict": b["summary"]["verdict"], "shots": b["summary"]["shots"],
                      "confidence": b["summary"]["confidence"], "vlm": b["summary"]["vlm"],
                      "report": str(out / "report.html")}, ensure_ascii=False, indent=2))
    return 0


def cmd_review(args) -> int:
    """Write review_tasks.json + review_answers.json so a multimodal agent can act as the VLM."""
    from .review import build_tasks

    out = Path(args.out_dir)
    b = read_json(out / "breakdown.json")
    set_lang(b.get("lang", "zh"))
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
    if args.lang:
        b["lang"] = args.lang
    set_lang(b.get("lang", "zh"))
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
    if not log["applied"] and not log["problems"]:
        print("答案文件里没有可并入的镜头（先按 review_tasks.md 填 review_answers.json）")
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


def _capsule_root(args, check: bool = True) -> Path:
    from .memory import capsule_root

    root = capsule_root(args.capsule_root)
    if check and not root.is_dir():
        raise SystemExit(T(f"找不到 capsule-cinema 仓库：{root}。用 --capsule-root 指定，或 rea-video prefs capsule_root <路径> 设成默认",
                           f"capsule-cinema repo not found: {root}. Pass --capsule-root, or set it once with: rea-video prefs capsule_root <path>"))
    return root


def cmd_remake_plan(args) -> int:
    from .integrations.capsule_cinema import build_remake_jobs

    bdir = Path(args.breakdown).parent
    root = _capsule_root(args)
    jobs = build_remake_jobs(read_json(Path(args.breakdown)), bdir, capsule_root=root,
                             engine=args.engine,  # None: keep the engine chosen at decompose time
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
    # capsule-root 只认命令行（jobs.json 可能是别人给的，不能让它决定跑哪个解释器、import 哪里的代码）
    root = _capsule_root(args, check=not args.dry_run)
    argv = ["--jobs", str(jobs), "--capsule-root", str(root)] + (["--only", args.only] if args.only else []) + (["--dry-run"] if args.dry_run else [])
    # 试跑不调用 capsule-cinema，用当前解释器即可
    python = sys.executable if args.dry_run and not args.python else _capsule_python(args.python, root)
    return _run_integration("run_remake.py", python, argv)


def cmd_capsule_draft(args) -> int:
    root = _capsule_root(args)
    argv = ["--breakdown", str(Path(args.breakdown).expanduser().resolve()), "--capsule-root", str(root)]
    argv += ["--capsule-name", args.capsule_name] if args.capsule_name else []
    argv += ["--capsule-display-name", args.capsule_display_name] if args.capsule_display_name else []
    argv += ["--write-capsule"] if args.write_capsule else []
    argv += ["--overwrite-capsule"] if args.overwrite_capsule else []
    return _run_integration("to_capsule.py", _capsule_python(args.python, root), argv)


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
    from .i18n import T, join

    b = read_json(Path(args.breakdown))
    set_lang(b.get("lang", "zh"))
    s = b["summary"]
    lines = [f"{b['source']['filename']} | {b['source']['duration']}s {b['source']['width']}x{b['source']['height']} {b['source']['fps']}fps",
             f"{T('结论', 'Verdict')}: {s['verdict']}", f"{T('置信度', 'Confidence')}: {s['confidence']}", f"VLM: {s.get('vlm') or vlm_note(b['analysis']['vlm'])}", ""]
    vc = b.get("video_context") or {}
    if vc.get("transcoded"):
        lines.append(T("平台转码: {p}（噪声类证据失效；原生 30fps 无重复帧: {n}）", "Platform transcode: {p} (noise evidence unusable; native 30fps without duplicate frames: {n})",
                       p=join(vc.get("platform", [])), n=vc.get("native30")))
    prov = b.get("provenance", {})
    if prov.get("aigc") or prov.get("hints"):
        lines.append(f"{T('元数据', 'Metadata')}: aigc={prov.get('aigc')} hints={prov.get('hints')}")
    from .aspects import shot_text
    from .memory import hint_for, patterns

    pats = patterns()
    for r in b["shots"]:
        base = r["base"]
        alt = sorted(base["probs"].items(), key=lambda kv: -kv[1])[1]
        det = r["deterministic"]["probs"]
        past = None if base["decided_by"] == "user" else hint_for(max(det, key=det.get), pats)
        mat = (r.get("material") or {}).get("origin_zh", "")
        second = T("(用户纠正)", "(user correction)") if base["decided_by"] == "user" else T("(次选 {l} {p:.2f})", "(runner-up {l} {p:.2f})", l=alt[0], p=alt[1])
        lines.append(f"#{r['index']:>2} {r['start']:7.2f}-{r['end']:7.2f} {base['label']:<14} {base['confidence']:.2f} {second} "
                     f"| {T('素材', 'material')}:{mat} | {T('叠加', 'overlays')}:{','.join(sorted({l['kind'] for l in r.get('layers', [])})) or '-'} | {r['features'].get('camera')}"
                     + (T("  ← 低置信，需要复核", "  ← low confidence, review it") if base["confidence"] < 0.6 else "")
                     + (f"  ← {base['uncertain']}" if base.get("uncertain") else "")
                     + (T("  ← 有分歧：{d}", "  ← disputed: {d}", d=base["disputed"]) if base.get("disputed") else "")
                     + (T("  ← 用户纠正过素材来源", "  ← material origin corrected by the user") if (r.get("material") or {}).get("user_corrected") else "")
                     + (f"  ← {past}" if past else "")
                     + (f" | {shot_text(r)}" if r["base"]["label"] in ("live_action", "avatar") and shot_text(r) else "")
                     + (T(" | 动效 {n} 个，元素截图 {f}", " | {n} motion events, element crops {f}", n=len(r["motion"].get("events", [])),
                          f=r["motion"]["elements_sheet"]) if r["base"]["label"] in ("code_render", "screen_capture")
                        and (r.get("motion") or {}).get("elements_sheet") else ""))
    if s.get("aspects"):
        lines += [""] + s["aspects"]
    from .entities import cast

    c = cast(b)
    if c["characters"] or c["scenes"]:
        lines.append("")
        for ch in c["characters"]:
            lines.append(f"{T('角色', 'Character')} {ch['id']} {ch['name']} | {ch['look']} | {T('镜头', 'shots')} {','.join(str(i) for i in ch['shots']) or '-'}")
        for sc in c["scenes"]:
            lines.append(f"{T('场景', 'Scene')} {sc['id']} {sc['where']} {sc['when']} | {sc['look']} | {T('镜头', 'shots')} {','.join(str(i) for i in sc['shots']) or '-'}")
    a = b.get("audio", {})
    if a.get("has_audio"):
        mu = a.get("music", {})
        lines += ["", f"{T('人声', 'Voice')}: {a.get('voice', {}).get('present')} ({a.get('voice', {}).get('ratio')}) | {T('音乐', 'Music')}: {mu.get('present')} "
                      f"{mu.get('tempo_bpm')}BPM {(mu.get('key') or {}).get('tonic', '')}{(mu.get('key') or {}).get('mode', '')} | "
                      f"{T('音效', 'SFX')}: {len((b.get('audio_plan') or {}).get('sfx_merged', []))} | {T('卡点', 'beat-synced')}: {a.get('beat_synced_edit')}"]
        if (b.get("sound_sources") or {}).get("summary_zh"):
            lines.append(f"{T('声音来源', 'Sound sources')}: " + b["sound_sources"]["summary_zh"])
        if (b.get("stems") or {}).get("ok"):
            lines.append(T("音轨: stems/original.wav（原声） stems/vocals.wav（人声） stems/music.wav（配乐）",
                           "Stems: stems/original.wav (original) stems/vocals.wav (voice) stems/music.wav (music)"))
    pk = b.get("packaging")
    if pk:
        tag = T("包装", "Packaging")
        lines += [""] + [f"{tag}: {x}" for x in (pk.get("summary_zh") or [T("没有检出后期叠加的文字或贴纸", "no overlaid text or stickers detected")])]
        low = [st for st in pk.get("stickers", []) if not st.get("in_picture") and st.get("confidence") in ("low", "vlm")]
        if low:
            lines.append(f"{tag}: " + T("需要看图确认的贴纸 ", "stickers to confirm by eye ") + join(f"{st['id']} {st['t0']:.1f}-{st['t1']:.1f}s" for st in low)
                         + T("（截图在 packaging/）", " (crops under packaging/)"))
        if pk.get("files"):
            lines.append(f"{T('包装文件', 'Packaging files')}: " + " ".join(pk["files"].values()))
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
    d.add_argument("--lang", choices=LANGS, help="报告、结论和 VLM 描述的语言：zh（默认）/ en；按用户提问的语言选，也可用 prefs lang 设成默认")
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
    r.add_argument("--capsule-root", help="capsule-cinema 仓库；默认 $CAPSULE_CINEMA_ROOT、prefs capsule_root，再退到 ~/code/github/capsule-cinema")
    r.add_argument("--engine", help="换用另一个视频引擎；默认沿用拆解时的引擎")
    r.add_argument("--mode", default="first_last_frame", choices=["first_last_frame", "image_to_video", "text_to_video"])
    r.add_argument("--labels", default="", help="只复刻这些底层类别（逗号分隔），默认 ai_video,cg_3d,live_action,avatar,anim_2d,stop_motion")
    r.set_defaults(func=cmd_remake_plan)

    rr = sub.add_parser("remake-run", help="用 capsule-cinema 执行 remake-plan 生成的任务（会计费，先 --dry-run）")
    rr.add_argument("jobs", help="remake-plan 输出的 jobs.json")
    rr.add_argument("--capsule-root", help="须与 remake-plan 时一致；默认同 remake-plan")
    rr.add_argument("--dry-run", action="store_true", help="只列出任务和参数，不调用模型")
    rr.add_argument("--only", default="", help="只跑这些镜头（逗号分隔）")
    rr.add_argument("--python", help="capsule-cinema 的 Python；默认 $CAPSULE_CINEMA_PYTHON 或 <capsule-root>/.venv/bin/python")
    rr.set_defaults(func=cmd_remake_run)

    cd = sub.add_parser("capsule-draft", help="用拆解结果生成 capsule-cinema 胶囊草稿")
    cd.add_argument("breakdown")
    cd.add_argument("--capsule-root", help="capsule-cinema 仓库；默认 $CAPSULE_CINEMA_ROOT、prefs capsule_root，再退到 ~/code/github/capsule-cinema")
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
    ar.add_argument("--lang", choices=LANGS, help="在这一步换报告语言：结论、证据和报告文字重新生成，VLM 已写好的描述和提示词保持原语言")
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

    for sp in sub.choices.values():  # also accept `rea-video decompose x.mp4 --env-file ...`
        sp.add_argument("--env-file", default=argparse.SUPPRESS, help=argparse.SUPPRESS)

    args = ap.parse_args(argv)
    setup_logging(args.verbose)
    _env(args)
    from .media import MediaError

    try:
        return args.func(args)
    except MediaError as exc:  # missing ffmpeg / unreadable video: one line, not a traceback
        hint = ""
        if "not found on PATH" in str(exc):
            hint = T("\n安装 ffmpeg：macOS `brew install ffmpeg`，Ubuntu/Debian `sudo apt install ffmpeg`",
                     "\ninstall ffmpeg: macOS `brew install ffmpeg`, Ubuntu/Debian `sudo apt install ffmpeg`")
        print(f"rea-video: {exc}{hint}", file=sys.stderr)
        if args.verbose:
            raise
        return 2
    except FileNotFoundError as exc:  # wrong path to a video / breakdown.json / answers file
        if args.verbose:
            raise
        print(f"rea-video: " + T(f"找不到文件：{exc.filename}", f"file not found: {exc.filename}"), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

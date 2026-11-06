# capsule-cinema 对接

`remake-run` 和 `capsule-draft` 会用 **capsule-cinema 自己的 Python 环境**运行包里的 `rea_video/integrations/run_remake.py`、`to_capsule.py`（它们会 import capsule-cinema 的 `lib/` 和 `scripts/`，并读取它的 `.env`）。解释器按 `--python` > `$CAPSULE_CINEMA_PYTHON` > `<capsule-root>/.venv/bin/python` 的顺序找。rea-video 本身只依赖 numpy/opencv/pillow/pyyaml。

```bash
CC=~/code/github/capsule-cinema          # capsule-cinema 仓库

# 1) 拆解（建议开 VLM，复用 capsule-cinema 的 Gemini 配置）
rea-video --env-file $CC/.env decompose ref.mp4 -o out/ref --vlm

# 2a) 生成胶囊草稿（不改 capsule-cinema 代码；通过 tool_factory 注入 rea-video 的拆解结果）
rea-video capsule-draft out/ref/breakdown.json \
    --capsule-root $CC --capsule-name my_ref_remake            # 加 --write-capsule 才落盘到 capsules/

# 2b) 复刻 AI 类镜头：生成任务 → 调 capsule-cinema 生成 → 按原时间线拼回并出对比片
rea-video remake-plan out/ref/breakdown.json --capsule-root $CC --engine seedance2.0
rea-video remake-run out/ref/remake/jobs.json --dry-run   # 先看任务
rea-video remake-run out/ref/remake/jobs.json             # 真正调用（会产生费用）
rea-video assemble out/ref/breakdown.json out/ref/remake/results.json
```

- AI 视频 / 3D / 实拍 / 数字人镜头：默认用原镜头的**首尾帧 + VLM 提示词**做 `first_last_frame` 生成（`--mode image_to_video` 只用首帧）。
- 静态图推拉、静帧：不调模型，`assemble` 用测得的缩放/平移参数在本地重建。
- 代码渲染、录屏镜头：默认保留原片（`keep_original`），重建请按报告中的文字轨/版式用 Remotion 实现。
- 只复刻部分镜头：`remake-run ... --only 2,5`（也可以写镜头 id：`--only shot_002,shot_005`）。有镜头没生成出视频时，命令以非 0 退出，失败详情在 results.json。
- capsule-cinema 不在默认路径（`~/code/github/capsule-cinema`）时，用 `rea-video prefs capsule_root <路径>` 设一次；或者每次都带 `--capsule-root`，`remake-run` 要和 `remake-plan` 一致；jobs.json 里记录的路径对不上会拒绝执行。

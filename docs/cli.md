# 命令行参考

平时不需要手敲这些命令：把仓库和视频交给 agent，它会按 [SKILL.md](../skills/rea-video/SKILL.md) 调用。这里留给想自己跑、或者想看 agent 在做什么的人。

## 安装

需要 Python ≥ 3.10 和 ffmpeg（macOS：`brew install ffmpeg`；Ubuntu：`apt install ffmpeg`）。

```bash
git clone <本仓库> && cd rea-video
pip install -e ".[ocr]"          # numpy / opencv / pillow / pyyaml / onnxruntime + 可选 OCR
rea-video --help
bash scripts/install_skill.sh    # 可选：装 CLI 并把 skill 链接到 ~/.claude/skills、~/.codex/skills、~/.agents/skills
```

手动装了 `[ocr]` 时，OCR 依赖会再装一套 `opencv-python`，和 rea-video 用的 `opencv-python-headless` 抢同一个 `cv2` 目录。装完跑一次：
`pip uninstall -y opencv-python && pip install --force-reinstall --no-deps "opencv-python-headless>=4.8,<5"`（`install_skill.sh` 会自动做）。

Claude Code 也可以按插件装 skill（CLI 仍需 `pip install`，skill 第一步会检查）：

```text
/plugin marketplace add JuneYaooo/rea-video
/plugin install rea-video@rea-video
```

首次拆解会自动下载约 67 MB 的人声分离模型（`~/.cache/rea-video/models`）。一条 30 秒视频不开 VLM 约 1 分钟出结果。

装好 skill 后，在 Claude Code / Codex / zcode 里直接说"帮我拆解这条视频 xxx.mp4，看看是不是 AI 做的"即可，agent 会按 [SKILL.md](../skills/rea-video/SKILL.md) 的流程跑：先看记忆 → 拆解 → 看图复核 → 按模板交付。

## 快速开始

```bash

# 1. 只做确定性取证（离线、免费）
rea-video decompose ref.mp4 -o out/ref

# 2. 加 VLM（建议，不强制）：让多模态大模型看画面，实拍/AI/3D 判断更准
#    任意 OpenAI 兼容的多模态模型都行，模型可写多个做备选
export REA_VLM_BASE_URL=https://.../v1 REA_VLM_API_KEY=... REA_VLM_MODEL=gemini-2.5-pro,gpt-4o
rea-video decompose ref.mp4 -o out/ref --vlm
#    或复用 capsule-cinema 的配置：rea-video --env-file ~/code/github/capsule-cinema/.env decompose ref.mp4 -o out/ref --vlm
#    VLM 调用全部失败时不会中断，报告和 `rea-video summary` 的 "VLM:" 一行会写明"全部调用失败，等同未开"

open out/ref/report.html

# 3. 没有 VLM，但 agent 自己能看图（zcode、Claude Code 等多模态 agent）：让 agent 当 VLM
rea-video review out/ref             # 生成逐镜看图任务和答案模板
rea-video apply-review out/ref --by zcode   # agent 填完答案后并入结论和报告

# 4. 用户纠正和偏好会被记住（存在 ~/.rea-video，可用 REA_VIDEO_HOME 改位置）
rea-video correct out/ref --shots 3 --label still_motion --note "这是定格动画"
rea-video prefs vlm on && rea-video prefs --note "报告尽量短"
rea-video memory

# 只剥离声音：stems/original.wav（原声）、vocals.wav（人声干声）、music.wav（配乐）
rea-video stems ref.mp4 -o out/ref
```

输出示例（混合片）：

```
结论：混合制作：代码/模板渲染 59% + AI 生成视频 41%；叠加层：字幕、标题（代码/剪辑软件合成）
#1 00:00.000 1.38s 代码/模板渲染 → R01 Remotion 重建
#2 00:01.375 2.50s AI 生成视频（24fps 源、无传感器噪声…）→ R07 首尾帧生成（capsule-cinema）
...
```

## 和 capsule-cinema 一起复刻

```bash
CC=~/code/github/capsule-cinema   # capsule-cinema 仓库；也可以设 CAPSULE_CINEMA_ROOT，或 rea-video prefs capsule_root $CC 设一次，之后不用再带 --capsule-root
rea-video remake-plan out/ref/breakdown.json --capsule-root $CC                  # AI 类镜头 → 首尾帧生成任务
rea-video remake-run out/ref/remake/jobs.json                                    # 调 capsule-cinema 生成（会计费，可先 --dry-run）
rea-video assemble out/ref/breakdown.json out/ref/remake/results.json            # 按原时间线拼回 + 对比片
rea-video capsule-draft out/ref/breakdown.json --capsule-root $CC --capsule-name my_remake
```

- 静态图推拉和静帧：不调模型，本地用测得的缩放和平移参数精确重建。
- 代码渲染和录屏：报告给出文字轨和版式，用 Remotion 重建。
- `capsule-draft`：通过 capsule-cinema 自带的 `tool_factory` 注入拆解结果，生成可复用的配方草稿，不需要改 capsule-cinema 的代码。

见 [capsule-cinema.md](capsule-cinema.md)。

## 命令

| 命令 | 作用 |
|---|---|
| `decompose VIDEO [--vlm] [--no-ocr] [--ocr-lang zh\|ja] [--lang zh\|en] [--no-packaging]` | 拆解，输出 breakdown.json、report.html/md、storyboard.jpg、每镜首尾帧，以及 `packaging/`（字幕 SRT、带样式的 ASS、包装时间轴、贴纸截图）；`--lang en` 让结论、报告、`summary` 输出和 VLM 描述都用英文（默认中文；agent 按用户提问的语言选，`rea-video prefs lang en` 可设成默认；breakdown.json 里的 `*_zh` 字段名保留，内容跟报告语言走）；`--no-packaging` 跳过包装层（省约每分钟 30–50 秒）；`--ocr-lang ja` 用日文识别模型读字幕和花字（首次使用自动下载约 10 MB 到 `$REA_VIDEO_MODELS`，离线时可用 `$REA_OCR_REC_MODEL` 指向本地模型），`rea-video prefs ocr_lang ja` 可设成默认 |
| `review OUT_DIR` | 给能看图的 agent 生成逐镜看图任务（review_tasks.json）和答案模板（review_answers.json） |
| `apply-review OUT_DIR [ANSWERS] [--by NAME] [--lang zh\|en]` | 把 agent 看图的答案和确定性结果融合，重写 breakdown.json 和报告；`--lang` 可以在这一步换报告语言（结论、证据和报告文字重新生成，VLM 已写好的描述和提示词保持原语言） |
| `correct OUT_DIR --shots N --label L [--real yes/no] [--note]` | 用户指出判错：改正结论和报告，并记入记忆（以后同一文件自动套用，同类镜头复核时提示） |
| `prefs [KEY VALUE] [--note TEXT]` | 用户偏好：默认引擎、是否默认开 VLM、VLM 配置文件、复核者名字、报告语言（`lang zh\|en`）、给 agent 的自由文字说明 |
| `memory [--export-labels YAML]` | 看记住了什么（偏好、常见纠正类型）；把纠正导出成评测样本 |
| `probe VIDEO` | 只看元数据线索（拍摄设备、AIGC 隐式标识、C2PA、编辑器签名） |
| `summary breakdown.json` | 紧凑打印结论，标出需要复核的低置信镜头 |
| `tiles VIDEO --start --end --every` | 按时间抽帧拼图，近距离复核 |
| `eval labels.yaml` | 在带标注的样本上评测准确率和切点 F1 |
| `capsule breakdown.json` | 导出 capsule-cinema 的视频分析 JSON |
| `remake-plan` / `assemble` | 生成复刻任务、拼回成片 |
| `remake-run JOBS [--dry-run] [--only 2,5\|shot_002] [--capsule-root]` | 用 capsule-cinema 执行复刻任务（会计费）；有镜头没生成出视频时退出码非 0 |
| `capsule-draft breakdown.json` | 生成 capsule-cinema 胶囊草稿 |

## 工作流（设计目标；目前完成到拆解和 AI 镜头复刻）

```
Ingest ─► Decompose ─► Video IR ─► Plan ─► Reconstruct ─► Verify ─► Remix
 导入      拆解/拉片     源码        路由     重建           差分验证   批量改写
```

| 阶段 | 状态 |
|---|---|
| Ingest、Decompose、Video IR（`breakdown.json`） | 已可用，即本仓库主体 |
| Plan | 已可用：每镜给出复刻路线；AI 类镜头生成 capsule-cinema 任务 |
| Reconstruct | 部分可用：AI 镜头交给 capsule-cinema，静态图推拉本地重建；代码层只给出文字轨和版式，还不生成 Remotion 工程 |
| Verify | 部分可用：`assemble` 拼回成片并输出对比视频；自动打分还没做 |
| Remix | 未开始 |

1. **Ingest（导入）**：probe、抽帧、分离音轨。
2. **Decompose（拆解）**：确定性 CV 和 VLM 分工。CV 负责精确的时间和位置：切镜、OCR 轨迹、分割、相机运动、节拍、字级对齐；VLM 负责语义：镜头意图、表演、风格。
3. **Video IR（源码）**：时间线 → 轨道 → 片段。每个片段标注渲染方式（`code` / `gen` / `footage` / `audio`），并附参数、证据和 unknowns。
4. **Plan（路由）**：读取 [能力地图](../rea_video/capabilities/README.md)，把每个生成单元路由到原语和模型，输出 Shot Recipe，包含成本预估和需要用户确认的节点。
5. **Reconstruct（重建）**：代码层用 Remotion 等渲染，生成层调用模型，音频层用 TTS、音乐、音效，最后合成。
6. **Verify（验证）**：检查切点对齐、OCR 文本一致性、布局 IoU、感知相似度、主体一致性、运动轨迹、节拍和口型，输出 scorecard，由 agent 循环修复得分最差的镜头。
7. **Remix（改写）**：换人、换货、换文案、换语言、换画幅时，只重新渲染受影响的层。

## 两种模式

- **fidelity（高保真复刻）**：目标是结构、节奏、运镜、文字和动效逐项对齐，用分数说话。
- **adapt（创意改编）**：保留原片"为什么有效"的关系，比如钩子、揭示、节奏，内容按新主题重写。

两种模式可以按层混用。例如节奏和运镜走 fidelity，人物和文案走 adapt。

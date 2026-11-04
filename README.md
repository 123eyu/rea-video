<div align="center">

# rea-video

逆向一切视频。

实拍口播、桌拍、AI 视频、3D、代码动效、混剪都能拆，<br>
逐个镜头告诉你画面、花字、剪辑和声音是怎么做的，再告诉你怎么照着做一条。

中文 | [English](README_en.md)

[![Stars](https://img.shields.io/github/stars/JuneYaooo/rea-video?style=flat)](https://github.com/JuneYaooo/rea-video/stargazers)
![Python](https://img.shields.io/badge/python-%E2%89%A53.10-blue)
![Agent](https://img.shields.io/badge/runs%20in-Claude%20Code%20%7C%20Codex-8A2BE2)

<img src="docs/cases/demo.gif" width="440" alt="左：TikTok 手机实拍原片；右：别人用 AI 换产品重做的版本">

左边是 TikTok 上的手机实拍原片，右边是别人用 AI 换了产品重做的版本。<br>
rea-video 判断：左边全部实拍，一个场景、两个机位就能拍完；右边全部 AI 生成，8 个镜头可以合并成 3 次生成。

</div>

## 能拆哪些视频

| 视频类型 | 常见例子 | 拆出什么 |
|---|---|---|
| 实拍 | 口播、桌拍、手持带货、vlog、探店 | 拍摄场次和机位，景别、运镜、布光（12 种方案附器材）、调色 |
| AI 视频 | 文生 / 图生视频、AI 短剧、AI MV | 判断依据，每镜反推的提示词，合并成几次生成、用哪个模型 |
| 数字人 | 人像被声音驱动说话、对口型 | 哪些镜头是数字人，需要的人像和音频 |
| 3D / 动画 | Blender / C4D 科普、产品动画、2D 动画、定格动画 | 用视频模型生成还是写 3D 代码渲染 |
| 代码 / 模板 | 文字动效、UI 演示、图表、PPT 式卡片 | 文字、版式、动效节奏，可以写成 Remotion 工程 |
| 录屏 / 截图 | 软件教程、网页演示 | 哪些是真实素材，复刻时要你自己录 |
| 混合 / 混剪 | AI 人物 + 代码界面 + 真实录屏，实拍 + AI 加工 | 每一镜分开判断，再按原时间线拼回 |

除了画面怎么做的，每条视频还会拆：

- 字幕和花字：每句字幕的起止时间（可导出 SRT / ASS），花字用什么颜色、描边、怎么出场
- 贴纸、表情包、画中画：放在哪、停多久
- 剪辑：在哪切、节奏多快、有没有卡节拍
- 声音：真人还是 AI 配音，配乐是 AI 做的还是曲库的、多少 BPM，音效落在哪一下
- 要你自己准备的素材：录屏、截图、产品图

## 快速开始

rea-video 是给 AI 助手用的。在 Claude Code、Codex 这类能运行命令的 agent 里说：

```text
安装 https://github.com/JuneYaooo/rea-video ，然后拆解这条视频：/path/to/video.mp4
```

agent 会自己装好命令行工具、读完拆解流程，然后从头跑完。电脑上需要有 ffmpeg 和 Python 3.10 以上。

跑完你会拿到：

- 一句话结论，比如「AI 视频 41% + 代码界面 59%，有 8 秒真实录屏，曲库配乐 122 BPM」
- 复刻方案，按实拍、AI 生成、代码分开写
- 完整报告 `report.html`：逐镜头截图、判断依据、提示词、拍法和声音拆解

配一个看视频的模型，Gemini 豆包都行，把接口地址和密钥告诉 agent 就行。配上之后实拍、AI、3D 分得更准，每个镜头还会反推出提示词。不配也能用，agent 自己能看图的话，会补看没把握的镜头。

## 案例

<table>
<tr>
<td width="50%" valign="top">
<a href="docs/cases.md#2-混合片ai-人物对话--代码界面--真实录屏"><img src="docs/cases/dual_role/storyboard.jpg"></a><br>
<b>混合片</b> · 19 秒 · 10 镜<br>
AI 人物对话 + 代码界面 + 8 秒真实录屏。5 个对话镜头被界面隔开，但同一个场景，一次生成就够。<br>
<a href="docs/cases/videos/dual_role.mp4">视频</a> · <a href="docs/cases/dual_role/report.md">报告</a>
</td>
<td width="50%" valign="top">
<a href="docs/cases.md#3-3d-科普片咸鸭蛋为什么会流油"><img src="docs/cases/salted_egg/storyboard.jpg"></a><br>
<b>3D 科普片</b> · 67 秒 · 21 镜<br>
全部 3D 渲染，AI 旁白。可以合并成 10 次视频生成，也可以让大模型写 Blender / Three.js 代码。<br>
<a href="docs/cases/videos/salted_egg.mp4">视频</a> · <a href="docs/cases/salted_egg/report.md">报告</a>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<a href="docs/cases.md#4-代码-ui-动效产品宣传片"><img src="docs/cases/v10/storyboard.jpg"></a><br>
<b>产品宣传片</b> · 70 秒 · 12 镜<br>
83% 是代码动效，12% 录屏。不需要视频模型，写一个 Remotion 工程就能做。<br>
<a href="docs/cases/videos/v10_oiioii_gen_coding_first.mp4">视频</a> · <a href="docs/cases/v10/report.md">报告</a>
</td>
<td width="50%" valign="top">
<a href="docs/cases.md#5-ai-音乐-mv歌是-ai-写的还是曲库的"><img src="docs/cases/qing_mv/preview.jpg"></a><br>
<b>AI 音乐 MV</b> · 165 秒 · 86 镜<br>
判出歌是 AI 生成的（实际是 Suno）。看图模型说是「影视剧实拍」的镜头，agent 从奏折上的伪汉字认出是 AI。<br>
<a href="docs/cases/videos/qing_mv.mp4">视频</a> · <a href="docs/cases/qing_mv/report.md">报告</a>
</td>
</tr>
</table>

## 准不准

按镜头时长算的「制作方式」准确率：

| | 调参集（15 条） | 留出集（16 条） | 公众号转码视频（10 条） |
|---|---|---|---|
| 只用工具（离线、免费） | 98.3% | 99.6% / 98.9% | 88.6% |
| + 看图模型（Gemini） | — | 99.6% / 99.8% | 99.6% |
| + agent 看图复核 | — | 99.6% / 99.8% | 100% |

原始文件只用工具基本够。从平台下载的视频压缩过，噪点证据没了，要靠看图才能回到 99% 以上。真实素材识别 97–99%，镜头切点全对。明细和复现方法在 [eval/RESULTS.md](eval/RESULTS.md)。

## 怎么判断的

![rea-video 流程](docs/rea-flow.svg)

1. 切镜头：把视频按镜头切开，声音拆成人声、配乐、音效。
2. 取证据：测画面（帧率规律、噪点、是不是整张图在推拉、文件里有没有 AIGC 标识）；看图（手指、文字、物理细节对不对）；听声音（BPM、调性、是唱还是说）。
3. 综合判断：AIGC 标识、帧率这类硬证据优先于「看起来像」。几方意见冲突时标出来，交给 agent 看图复核。
4. 出复刻方案：按目标视频模型的实际能力分批，比如单次能生成多长、能不能一次出多个镜头、能吃几张参考图。

## 常见问题

<details>
<summary>和 Hypit 这类一键复刻工具有什么区别？</summary>

[Hypit](https://github.com/hypit-ai/hypit) 拿一条参考视频直接做一条新片：agent 看抽帧理解原片，再用它接入的模型（Seedance、PixVerse、MiniMax、Wan 等）生成画面，字幕和动效用 HTML 渲染出来。

它不区分原片是怎么做的。原片是实拍的，它照样按自己的流程重做，不会告诉你原片几个机位、怎么打光。AI 视频能做到什么程度，取决于它接了哪些模型：没有可灵、Veo，也没有专门的数字人和 3D；不生成 AI 配乐，配乐要自己准备。它最顺手的是口播、播客、采访这类跟着台词走的视频，纯音乐卡点、产品动效、电影感短片要弱一些。

rea-video 不直接出片。它先逐个镜头判断是拍的、AI 生成的还是代码做的，再分别给拍摄方案、提示词或代码思路。想马上做一条同款，用 Hypit 更快；想弄清原片怎么做、怎么少花钱做出来，用 rea-video。两个可以一起用。

</details>

<details>
<summary>一定要配看视频的模型吗？要花多少钱？</summary>

不一定。只用工具是离线、免费的，原始文件的准确率已经很高。从平台下载、压缩过的视频建议配一个能看视频的模型（Gemini、豆包都行），或者用本身能看图的 agent。模型按你用的服务计费。自动生成视频（capsule-cinema）会先免费试跑一遍，你确认后才会正式调用模型。

</details>

<details>
<summary>能自动把整条视频复刻出来吗？</summary>

部分可以。AI 镜头装了 [capsule-cinema](https://github.com/JuneYaooo/cheap-claude-video) 可以自动生成并拼回原时间线；实拍镜头要你按拍摄方案去拍；代码镜头要 agent 写 Remotion 工程。详见 [docs/replicate.md](docs/replicate.md)。

</details>

<details>
<summary>可以拿别人的视频直接搬运吗？</summary>

不可以。rea-video 用来学习视频的结构、节奏和做法，再用你有权使用的素材重新制作。请勿直接搬运他人的画面、音乐、角色或肖像。投放时请遵守平台规则和当地的 AI 生成内容标识要求。

</details>

## 文档

- [docs/what-it-detects.md](docs/what-it-detects.md)：能拆出什么（10 类画面、拍法、打光、调色、声音）
- [docs/replicate.md](docs/replicate.md)：拿到报告后怎么复刻
- [docs/cases.md](docs/cases.md)：案例详情
- [docs/decompose.md](docs/decompose.md)：判断规则
- [docs/cli.md](docs/cli.md)：命令行用法、和 capsule-cinema 的对接
- [rea_video/capabilities/](rea_video/capabilities/README.md)：各家视频 / 图像 / 音频模型的能力表，复刻方案按它选模型
- [eval/RESULTS.md](eval/RESULTS.md)：评测结果

## 社区

欢迎来 [linux.do](https://linux.do/) 交流使用体验、拆解案例和复刻思路。

## 致谢

思路来自 [REA（Reverse Engineer Anything）](https://github.com/morluto/rea)：从现象追到实现，结论附证据，用可测量的方式验证。

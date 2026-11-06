# Video breakdown report: v10.mp4

> English translation of [report.md](report.md), the Markdown report rea-video generated for this video. Section order and content follow the tool output. Text recognized on screen (the "text track" lines) is kept in the original Chinese, since that is what appears in the frame.

**Verdict**: mixed production: code / template rendering 83% + screen recording / screenshot 12% + still-image push / pan 5%; overlays: captions, title (composited in code / an editor); real material used: embedded video clips (33.4 s), logo / brand mark (22.4 s), UI screenshots (16.8 s), screen recording (8.6 s), real photos (7.1 s); audio: BGM at 112.3 BPM (library music) + 6 sound effects

- Duration 70.0 s · 1280×720 · 30.0 fps · 16:9
- 12 shots, 5.83 s average; transitions: cut×3, dissolve×7, fade×1, start×1
- Confidence (duration-weighted): 96%; method: deterministic forensics fused with a vision model (VLM)
- VLM active (gemini-3.1-pro-preview, gemini-3.1-pro-preview-pc, gcp-gemini-3-pro-preview)

![storyboard](storyboard.jpg)

## Production method share

| Underlying picture | Duration | Share |
|---|---|---|
| Code / template rendering | 58.27 s | 83% |
| Screen recording / screenshot | 8.57 s | 12% |
| Still-image push / pan (Ken Burns) | 3.17 s | 4% |

## Remake plan

**11 code-rendered / screen-recording shots → 1 code project (2 segments); 1 still-image push / still-frame shot → local rebuild**


### Code compositing

One Remotion / HTML project rebuilt from the text tracks and layout (text and UI 100% controllable; changing copy means changing data). An LLM can write this project directly.

- Segment 1: shots #1, #2, #3, #4, #5, #6, #7 (0.0–41.2 s)
- Segment 2: shots #9, #10, #11, #12 (44.4–70.0 s); #10 uses a real UI screen recording

### Local rebuild

- #8 still-image push / pan, 3.2 s: one image + the measured zoom / pan parameters, rendered directly with ffmpeg

## Framing, lighting and editing

- Editing: 9.4 cuts per minute, 5.83 s average shot; no live-action shots

- Note: contrast ratio, softness, color temperature and shot size are measured on the subject's pixels (the face when there is one, otherwise the sharpest region, which is an estimate); platform transcoding crushes shadows, so softness and fill read conservative; angle, light source type, catchlight and rim come from visual review. Where measurement and visual review disagree, both are listed.

## Metadata clues

- Encoder: `Lavf58.20.100`
- Platform: WeChat transcode

## Audio breakdown

![audio](audio.png)

- Overall loudness −17.4 dBFS, peak −1.4 dBFS
- **Voice**: none / very little, 5% of duration, fundamental about 247.8 Hz (reads female)
- **Background music**: 99% of duration (0.0–69.5 s), about 112.3 BPM (or 56.2 / 224.7), key B minor (confidence 0.524), section changes at 4.0 s, 19.5 s, 38.5 s, 55.5 s, 65.5 s
- **Cuts vs beat**: 36% of cuts land on a beat (random baseline about 26%)

**Audio source: AI-generated or existing material**

- **Conclusion**: video type: music only (no voice) → music: library music; sound effects: added in post from a sound library / editor (leaning, to be confirmed)
- **Separated stems**: `stems/original.wav` (original), `stems/vocals.wav` (dry voice; transient effects land here too), `stems/music.wav` (music + ambience)
- Video form: other; AI picture 0%, live footage 0%
- **Background music**: library music (existing_library 67%, ai_generated 21%, popular_song 12%)
  - The music is a bed under the picture: for an ordinary video the bed is most likely from a library (prior)
  - VLM listening judgment: library music
  - Music and video end together: cut to length or custom-made (either source possible, weak evidence)
  - How to confirm: on the Douyin / Xiaohongshu page check the music tag: a song title → existing track; "original sound by @author" → uploaded by the author (for music videos this is usually an AI song)
  - How to confirm: run Soda Music / QQ Music song recognition or ACRCloud: a hit means an existing song
  - How to confirm: listen: AI songs often have slurred diction, thin metallic highs and lyrics that track the picture closely; library beds are mostly instrumental, standard structure, cut off or faded at the end
- **Sound effects**: added in post from a sound library / editor (library_editor 57%, ai_native 29%, live_sync 14%)
- Per-segment native-audio check: background change 4.3 dB at cuts, 4.8 dB within shots (ratio 0.89) → sound is continuous across cuts, laid over the whole piece in post

**Sound effects** (6; source: vlm = heard by the model, deterministic = signal-detected candidate, low confidence)

| Time | Type | Description | Matching picture | Source |
|---|---|---|---|---|
| 0.80 s | whoosh | light whoosh of a UI swipe | transition | vlm |
| 7.80 s | click | crisp click of the mouse on the Generate button | action | vlm |
| 25.80 s | click | click when sending the prompt | action | vlm |
| 51.50 s | typing | keyboard typing while entering numbers | action | vlm |
| 60.50 s | pop | soft bubble pop as particles gather and burst outward | action | vlm |
| 68.49 s | pop |  |  | deterministic |

**Audio remake plan**

- music (A03-music): tech-flavored modern pop-electronic, upbeat commercial showcase music; professional, innovative, bright, composed; 112.3 BPM; B minor → the original leans library: search a library by BPM / mood / key, or generate a royalty-free track in a similar style with AI
- sfx (A04-sfx): 6 effects → place them by timestamp: capsule-cinema SoundEffectsTool / a sound library, or synthesize them procedurally like the plush recipe (pitch aligned to the BGM key)
- ambience (A04-sfx): none (clean commercial motion-graphics render) → ambience stock or a video-to-audio model
- Mix: no narration; the whole piece rides on commercial synth BGM, with a few crisp effects layered at key UI interaction points

## Structure and copy (VLM)

- Summary: a launch promo for OiiOi's video remake feature, showing an AI workflow that breaks a reference video down frame by frame and batch-generates multiple versions of marketing short videos.
- Form: other; hook: minimalist animated large type reveals the core selling point "OiiOi 视频复刻 现已上线" ("OiiOi video remake, now live"), paired with crisp tech sound effects and a driving modern electronic beat to grab attention.
- Narration: none; music: tech-flavored modern pop-electronic, upbeat commercial showcase music; captions: centered animated large-type copy, key words highlighted in a purple-blue gradient, fine modern typeface, no outline and no background box
- Overall judgment (VLM): pure computer graphics / 3D motion-graphics rendering: a SaaS product feature promo built from 3D-perspective UI mockup layouts, eased text animation and a synth score. (Note: the per-shot forensics read #8 as a still-image push on a screenshot and #10 as a real screen recording rather than rendered graphics; see those shots.)
  - 0.0–8.87 s · reveals the product theme and the feature launch, shows the product UI · OiiOi 视频复刻 现已上线 ("OiiOi video remake, now live")
  - 8.87–15.93 s · core selling point: a new way to remake hit videos, shows the frame-by-frame analysis UI · 开启 一种 复刻爆款 的新方式 ("A new way to remake hits")
  - 15.93–26.7 s · explains the core mechanism: frame-by-frame breakdown to read the structure of a hit, then a natural-language instruction to swap in your product · 逐帧拉片，读懂 每一个 爆款结构 ("Frame by frame, read every hit's structure")
  - 26.7–41.2 s · capability matrix: unlock e-commerce selling, brand ads and ad-delivery videos, generate storyboards and material in real time · 解锁 电商带货 · 广告片 · 投放视频 / 实时生成 分镜 与 素材 ("Unlock e-commerce selling · brand ads · ad videos / Generate storyboards and material in real time")
  - 41.2–55.5 s · result comparison and batch production: original vs remake side by side, batch-generate versions on demand · 以及 按需 批量生成的 投放版本 ("And ad versions batch-generated on demand")
  - 55.5–70.0 s · wrap-up and brand close: remaking hits is easier, brand motion freeze · 现在，复刻任何爆款 都更简单 / 成片 也更懂 你的品牌 ("Now remaking any hit is easier / and the final cut understands your brand better")

## Real material in the frame

10 shots, 68.0 s (97%), contain real material (screen recordings, screenshots, photos, embedded video). A remake needs the original files; they cannot be replaced by generated output:

- Shot #1 (00:00.000): embedded video clip, partial frame, the reference video embedded in the video player on the left of the UI, showing a woman holding a white cup
- Shot #2 (00:08.867): real photo, partial frame, several thumbnails of people videos embedded in the UI table
- Shot #3 (00:15.933): logo / brand mark, partial frame, the colored 'OiiOi' wordmark centered at the top
- Shot #6 (00:28.367): embedded video clip, partial frame, the blurred people video inside the 'E-commerce selling' box on the left
- Shot #7 (00:38.933): embedded video clip, partial frame, the e-commerce host's selling clip inside the left card
- Shot #7 (00:38.933): embedded video clip, partial frame, the perfume brand ad clip inside the middle card
- Shot #7 (00:38.933): embedded video clip, partial frame, the outdoor jogging clip inside the right card
- Shot #8 (00:41.200): UI screenshot, full frame
- Shot #8 (00:41.200): UI screenshot, partial frame, screenshot of the Oiioi video-remake and batch-delivery software's operating interface
- Shot #8 (00:41.200): embedded video clip, partial frame, the video still / material of a selling host holding a thermos embedded in the UI
- Shot #9 (00:44.367): logo / brand mark, partial frame, the oiioi brand mark in the bottom-left corner
- Shot #10 (00:46.933): UI screenshot, full frame
- Shot #10 (00:46.933): screen recording, partial frame, the whole web operating interface
- Shot #10 (00:46.933): embedded video clip, partial frame, the reference video shown at the top of the UI (a woman holding a thermos)
- Shot #11 (00:55.500): UI screenshot, partial frame, a blurred screenshot of the software interface that flashes between text transitions
- Shot #12 (01:00.600): logo / brand mark, partial frame, the colored gradient ring logo and the OiiOi brand mark

## Shot list

| # | Time | Duration | Underlying picture | Confidence | Material | Overlays | Camera | Remake route |
|---|---|---|---|---|---|---|---|---|
| 1 | 00:00.000 | 8.87 s | Code / template rendering | 99% | Mixed (real material): embedded video clip | — | Smooth move | R01-code-graphics → code_render_spec |
| 2 | 00:08.867 | 7.07 s | Code / template rendering | 99% | Mixed (real material): real photo | — | Smooth move | R01-code-graphics → code_render_spec |
| 3 | 00:15.933 | 10.43 s | Code / template rendering | 95% | Mixed (real material): logo / brand mark | — | Static | R01-code-graphics → code_render_spec |
| 4 | 00:26.367 | 0.33 s | Code / template rendering | 99% | Producer-rendered | — | Smooth move | R01-code-graphics → code_render_spec |
| 5 | 00:26.700 | 1.67 s | Code / template rendering | 95% | Producer-rendered | — | Static | R01-code-graphics → code_render_spec |
| 6 | 00:28.367 | 10.57 s | Code / template rendering | 99% | Mixed (real material): embedded video clip | — | Static | R01-code-graphics → code_render_spec |
| 7 | 00:38.933 | 2.27 s | Code / template rendering | 95% | Mixed (real material): embedded video clip; to be confirmed whether real: photo / image material | — | Static | R01-code-graphics → code_render_spec |
| 8 | 00:41.200 | 3.17 s | Still-image push / pan (Ken Burns) | 80% | User's real material: UI screenshot, embedded video clip | Captions, title | Whole-image push / pan | R17-still-motion → local_ffmpeg |
| 9 | 00:44.367 | 2.57 s | Code / template rendering | 91% | Mixed (real material): logo / brand mark | — | Static | R01-code-graphics → code_render_spec |
| 10 | 00:46.933 | 8.57 s | Screen recording / screenshot | 98% | User's real material: UI screenshot, screen recording, embedded video clip | — | Static | R02-screen-demo → code_render_spec |
| 11 | 00:55.500 | 5.10 s | Code / template rendering | 92% | Mixed (real material): UI screenshot | — | Static | R01-code-graphics → code_render_spec |
| 12 | 01:00.600 | 9.40 s | Code / template rendering | 99% | Mixed (real material): logo / brand mark | — | Smooth move | R01-code-graphics → code_render_spec |

## Shot details

### #1 00:00.000–00:08.867 · Code / template rendering; introduces real material (embedded video clip)

![shot_001](shots/shot_001.jpg)

- Probabilities: code / template rendering 98%, 3D rendering 1%, 2D animation 0% (fused)
- Material: mixed (real material): embedded video clip
- Likely tool: After Effects / UI motion template
- In-shot motion beat: 4.53 s
- 50% of adjacent frames are exact duplicates, only local elements move (typical of template / motion-graphics animation, or local motion over a held frame)
- Rendered texture: flat color blocks 80%, 95% of pixels use only 6 colors, horizontal / vertical straight edges 8%
- 97% of background pixels are identical frame to frame, only local elements move: 2D compositing / code-animation signature
- Duplicate frames follow a 24→60 pattern (50%, period 1): source was 24/25 fps then transcoded, typical of AI video, 3D / animation renders or film footage
- [VLM] 00:00–00:04 text fade-in / fade-out animation on a pure white background
- [VLM] 00:05–00:08 UI showcase with a 3D perspective, not a real screen filmed
- [VLM] Smooth, programmatic camera push / pull / pan
- [VLM] Mouse cursor animation moving in a straight line at constant speed
- Picture: opens with purple text fading in on a white background, then transitions to a software UI with a 3D perspective. A reference video plays on the left of the UI, the operating panel is on the right, the mouse cursor moves and clicks the "开始复刻" ("Start remake") button, and the camera slowly pans and pulls back to show the whole UI.
- Text track (in-frame text / middle): OiiOi视频复刻现已上线 / 开始复刻
- Text track (in-frame text / middle): 考视频.mp
- Text track (in-frame text / middle): O / a
- Remake: code rendering: rebuild from the text tracks and layout in Remotion / HTML, 100% controllable, no generative model needed; the user must supply the real material: embedded video clip (partial frame)

### #2 00:08.867–00:15.933 · Code / template rendering; introduces real material (real photo)

![shot_002](shots/shot_002.jpg)

- Probabilities: code / template rendering 86%, 3D rendering 13%, 2D animation 0% (fused)
- Material: mixed (real material): real photo
- Likely tool: After Effects
- 52% of adjacent frames are exact duplicates, only local elements move (typical of template / motion-graphics animation, or local motion over a held frame)
- Rendered texture: flat color blocks 91%, 95% of pixels use only 1 color, horizontal / vertical straight edges 7%
- 97% of background pixels are identical frame to frame, only local elements move: 2D compositing / code-animation signature
- Duplicate frames follow a 24→60 pattern (52%, period 1): source was 24/25 fps then transcoded, typical of AI video, 3D / animation renders or film footage
- [VLM] 00:00–00:03 pure typographic animation
- [VLM] 00:04–00:15 UI showcase with a 3D perspective effect
- [VLM] UI elements (text, table, thumbnails) are sharp and undistorted, typical motion-graphics compositing
- Picture: text fades in one line at a time on a pure white background, then cuts to a video-analysis software UI with a 3D perspective, shown with a camera pan.
- Text track (in-frame text / bottom): 特写 / 卖点·倒入热水 / 中 / 证明·12小时仍赠热气
- Text track (in-frame text / bottom): 0.0~2.1s / 近景 / 场景·通勤与办公
- Text track (in-frame text / bottom): 镜头01 / 2.1~4.8s / 镜头02 / 4.8-7,0s
- Text track (in-frame text / middle): 开启 一种 复刻爆款 / 参考视频.mp
- Remake: code rendering: rebuild from the text tracks and layout in Remotion / HTML, 100% controllable, no generative model needed; the user must supply the real material: real photo (partial frame)

### #3 00:15.933–00:26.367 · Code / template rendering; introduces real material (logo / brand mark)

![shot_003](shots/shot_003.jpg)

- Probabilities: code / template rendering 94%, screen recording / screenshot 4%, 3D rendering 1% (fused)
- Material: mixed (real material): logo / brand mark
- Likely tool: After Effects / Remotion
- 96% of adjacent frames are exact duplicates, only local elements move (typical of template / motion-graphics animation, or local motion over a held frame)
- Rendered texture: flat color blocks 89%, 95% of pixels use only 1 color, horizontal / vertical straight edges 28%
- 99% of background pixels are identical frame to frame, only local elements move: 2D compositing / code-animation signature
- Re-transcoded by the platform (WeChat transcode), so sensor noise has been crushed away: noise-based evidence is void; live footage vs AI rests mainly on frame rate and picture content
- [VLM] Flat UI interaction animation on a pure white background
- [VLM] Colored vector logo and a search box with a gradient border
- [VLM] Character-by-character typewriter effect, no camera noise or live-footage traits at all
- Picture: minimalist white background, the colored 'OiiOi' mark in the center, and below it an input box where a prompt for analysing a product-selling video is typed out.
- Text track (in-frame text / middle): Oiioi
- Text track (in-frame text / middle): 问问0ii，想复刻什么？ / 参考这条带货视频，把产品换成我的保温杯，保留原片的 / 参考这条带货视频，把产品换成我的保温杯，保留原片的节奏、锁头 / 和类点结构，再出一版广告片和三条投放素材
- Remake: code rendering: rebuild from the text tracks and layout in Remotion / HTML, 100% controllable, no generative model needed; the user must supply the real material: logo / brand mark (partial frame)

### #4 00:26.367–00:26.700 · Code / template rendering

![shot_004](shots/shot_004.jpg)

- Probabilities: code / template rendering 96%, 3D rendering 2%, 2D animation 1% (fused)
- Material: producer-rendered
- Likely tool: After Effects / UI motion tool / CapCut (JianYing)
- Rendered texture: flat color blocks 82%, 95% of pixels use only 4 colors, horizontal / vertical straight edges 27%
- Re-transcoded by the platform (WeChat transcode), so sensor noise has been crushed away: noise-based evidence is void; live footage vs AI rests mainly on frame rate and picture content
- [VLM] The frame is a pure UI design with text, a colored logo and a dialog-like graphic element
- [VLM] The frame sequence shows a simple darkening transition (like a fade to black), with no 3D depth or real physical motion
- [VLM] Entirely 2D animation made in code or post software (such as AE)
- Picture: a UI on a light-gray background darkens. A colored "Oi Oi" logo sits in the center, below it a rounded dialog box with Chinese copy about short-video production, and a blue play button in the bottom-right corner. The whole frame goes from bright to dark.
- Text track (in-frame text / middle): Oiioi
- Text track (in-frame text / middle): 参考这条带货视频，把产品换成我的保温杯，保留原片的节奏、锁头 / 和类点结构，再出一版广告片和三条投放素材 / 参考这条带货视频，热产品换成我的保温杯，保留原片的节奏、锁头 / 和类点结构，两出一广告片和三条投放素材
- Remake: code rendering: rebuild from the text tracks and layout in Remotion / HTML, 100% controllable, no generative model needed

### #5 00:26.700–00:28.367 · Code / template rendering

![shot_005](shots/shot_005.jpg)

- Probabilities: code / template rendering 94%, screen recording / screenshot 4%, 3D rendering 1% (fused)
- Material: producer-rendered
- Likely tool: After Effects
- 96% of adjacent frames are exact duplicates, only local elements move (typical of template / motion-graphics animation, or local motion over a held frame)
- Rendered texture: flat color blocks 77%, 95% of pixels use only 5 colors, horizontal / vertical straight edges 37%
- 98% of background pixels are identical frame to frame, only local elements move: 2D compositing / code-animation signature
- Re-transcoded by the platform (WeChat transcode), so sensor noise has been crushed away: noise-based evidence is void; live footage vs AI rests mainly on frame rate and picture content
- [VLM] Dark-blue grid background with a glowing UI input box
- [VLM] Centered plain-text logo and a prompt dialog
- [VLM] The frame is essentially static, standard 2D UI motion design
- Picture: a dark-blue tech-style grid background with the brand logo and an AI prompt input box in the center; the frame is static.
- Text track (in-frame text / middle): Oiioi
- Text track (in-frame text / middle): 参考这条带货视频，把产品换成我的保温杯，保留原片的节奏、锁头 / 和类点结构，再出一版广告片和三条投放素材 / 参考这条带货提频，把产品换成我的保温杯，保留原片的节奏、锁头 / 参考这条敬被，把产品换成我的保温，保量片的节赛、镜头
- Remake: code rendering: rebuild from the text tracks and layout in Remotion / HTML, 100% controllable, no generative model needed

### #6 00:28.367–00:38.933 · Code / template rendering; introduces real material (embedded video clip)

![shot_006](shots/shot_006.jpg)

- Probabilities: code / template rendering 98%, 3D rendering 1%, 2D animation 0% (fused)
- Material: mixed (real material): embedded video clip
- Likely tool: After Effects
- Rendered texture: flat color blocks 81%, 95% of pixels use only 2 colors, horizontal / vertical straight edges 22%
- 97% of background pixels are identical frame to frame, only local elements move: 2D compositing / code-animation signature
- Re-transcoded by the platform (WeChat transcode), so sensor noise has been crushed away: noise-based evidence is void; live footage vs AI rests mainly on frame rate and picture content
- [VLM] Solid background with regular grid lines
- [VLM] Layout and entrance animation of text and UI elements
- [VLM] No real physical light and shadow, no camera motion
- Picture: motion graphics on a dark background, showing in turn text, a code block, and the generation-progress UI of three phone screens.
- Text track (in-frame text / bottom): 电商修货 / 生成中43% / 生中0%
- Text track (in-frame text / middle): Oiioi / 复脚本-保温杯附资·9：16 / ref=拉片（参考视频，np4”）5银头·快-慢快 / shot_01=Shot[t=0.0-2.15”，=特”，内容=主杯·开场子”
- Text track (in-frame text / middle): 解锁电商带货·广告片·投放视频
- Text track (in-frame text / middle): 品牌广告 / 生续中17%
- Remake: code rendering: rebuild from the text tracks and layout in Remotion / HTML, 100% controllable, no generative model needed; the user must supply the real material: embedded video clip (partial frame)

### #7 00:38.933–00:41.200 · Code / template rendering; introduces real material (embedded video clip)

![shot_007](shots/shot_007.jpg)

- Probabilities: code / template rendering 93%, screen recording / screenshot 4%, 3D rendering 1% (fused)
- Material: mixed (real material): embedded video clip; to be confirmed whether real: photo / image material
- Likely tool: After Effects / Remotion
- Rendered texture: flat color blocks 54%, 95% of pixels use only 91 colors, horizontal / vertical straight edges 35%
- Re-transcoded by the platform (WeChat transcode), so sensor noise has been crushed away: noise-based evidence is void; live footage vs AI rests mainly on frame rate and picture content
- [VLM] Card UI animation on a dark grid-textured background
- [VLM] Three cards show generation progress bars and completed-state pill buttons
- [VLM] Sample video thumbnails in different styles nested inside the cards
- Picture: on a dark tech background, three video cards (e-commerce selling, brand ad, feed ad) go from loading progress to an all-complete state in a UI animation.
- Text track (in-frame text / bottom): 电商货 / 生成中53% / 生中0% / 电商修货
- Text track (in-frame text / middle): 品牌广告 / 生续中25% / 生央中84%
- Remake: code rendering: rebuild from the text tracks and layout in Remotion / HTML, 100% controllable, no generative model needed; the user must supply the real material: embedded video clip (partial frame), embedded video clip (partial frame), embedded video clip (partial frame)

### #8 00:41.200–00:44.367 · Still-image push / pan (screenshot) + code / editor overlays (captions, title); introduces real material (UI screenshot, embedded video clip)

![shot_008](shots/shot_008.jpg)

- Probabilities: still-image push / pan 80%, screen recording / screenshot 15%, code / template rendering 2% (fused)
- Still-frame source: screenshot
- Material: user's real material: UI screenshot, embedded video clip
- The whole frame moves as a single rigid transform (100% inliers, residual 0.07 px, no local motion) → still-image push / pan: zoom −0.1%/s, pan 3 px/s
- Rendered texture: flat color blocks 52%, 95% of pixels use only 53 colors, horizontal / vertical straight edges 33%
- Dense fine high-frequency detail (small text / UI) on a flat background, like a screenshot or document
- [VLM] The frame is a static screenshot of a web product UI
- [VLM] Elements inside the frame are static; the only motion is a slow planar zoom and pan of the whole (Ken Burns effect)
- [VLM] The UI contains a frozen mouse pointer and a video comparison module
- Picture: a screenshot of a web UI showing the operating panel of AI video-remake software; the whole frame slowly pushes in and enlarges.
- Text track (captions / bottom): 价对出 / 导出 / 放对比 / 质货对比
- Text track (captions / bottom): 批量投放版本 / 在网一客爆款结构上，院检放宽求生症多个版本 / 在网一套司款继构上，按投放需求生或多个版本 / 在网一需限款场构上，按投放需求生或多个版本
- Text track (captions / bottom): 生欢款量 / 业成数量 / 业欢欢量
- Text track (captions / middle): 复制或片 / 考频 / 复刻成片 / 少考频
- Remake: still-image push / pan: reproduce exactly in local ffmpeg with one image + the measured zoom / pan parameters; the user must supply the real material: UI screenshot (full frame), UI screenshot (partial frame), embedded video clip (partial frame)

### #9 00:44.367–00:46.933 · Code / template rendering; introduces real material (logo / brand mark)

![shot_009](shots/shot_009.jpg)

- Probabilities: code / template rendering 90%, screen recording / screenshot 8%, 3D rendering 1% (fused)
- Material: mixed (real material): logo / brand mark
- Likely tool: After Effects
- 89% of adjacent frames are exact duplicates, only local elements move (typical of template / motion-graphics animation, or local motion over a held frame)
- Rendered texture: flat color blocks 96%, 95% of pixels use only 1 color, horizontal / vertical straight edges 21%
- 99% of background pixels are identical frame to frame, only local elements move: 2D compositing / code-animation signature
- Re-transcoded by the platform (WeChat transcode), so sensor noise has been crushed away: noise-based evidence is void; live footage vs AI rests mainly on frame rate and picture content
- [VLM] Minimalist white background with light-purple text fading in dynamically
- [VLM] Brand logo and prompt text in the bottom-left corner, small-print notes in the bottom-right
- [VLM] Typical motion-graphics / web demo card animation
- Picture: on a white background, light-purple centered text appears dynamically, with fine explanatory typesetting and a logo below; minimalist business showcase style.
- Text track (in-frame text / bottom): 出一短广张片扣三能搜欧系
- Text track (in-frame text / middle): 以及 / 以及按需批量生成的 / 以及按需批量生成的投放版本
- Remake: code rendering: rebuild from the text tracks and layout in Remotion / HTML, 100% controllable, no generative model needed; the user must supply the real material: logo / brand mark (partial frame)

### #10 00:46.933–00:55.500 · Screen recording / screenshot; introduces real material (UI screenshot, screen recording, embedded video clip)

![shot_010](shots/shot_010.jpg)

- Probabilities: screen recording / screenshot 98%, code / template rendering 0%, 3D rendering 0% (fused)
- Material: user's real material: UI screenshot, screen recording, embedded video clip
- Likely tool: screen-recording software
- In-shot motion beat: 51.33 s
- 58% of adjacent frames are exact duplicates, only local elements move (typical of template / motion-graphics animation, or local motion over a held frame)
- Rendered texture: flat color blocks 66%, 95% of pixels use only 6 colors, horizontal / vertical straight edges 34%
- 99% of background pixels are identical frame to frame, only local elements move: 2D compositing / code-animation signature
- Duplicate frames follow a 24→60 pattern (58%, period 1): source was 24/25 fps then transcoded, typical of AI video, 3D / animation renders or film footage
- [VLM] A real mouse cursor is visible moving in the frame
- [VLM] Continuous typing and deleting in the input box (entering 3, 12, 30 and so on)
- [VLM] Overall a standard web UI layout
- Picture: a screen recording of a web UI showing the batch video-version generation flow; the user edits the generation count in the input box several times.
- Text track (in-frame text / bottom): 累材条数 / 2 / 1 / 预计完播率
- Text track (in-frame text / bottom): 12小时长效保温 / 一键开盖·单手可喝
- Text track (in-frame text / bottom): 画幅 / 9:16竖屏 / 西帽
- Text track (in-frame text / bottom): 素材条数 / 6
- Remake: screen recording / screenshot: rebuild from a real UI screen recording or web screenshot; the user must supply the real material: UI screenshot (full frame), screen recording (partial frame), embedded video clip (partial frame)

### #11 00:55.500–01:00.600 · Code / template rendering; introduces real material (UI screenshot)

![shot_011](shots/shot_011.jpg)

- Probabilities: code / template rendering 91%, screen recording / screenshot 8%, 3D rendering 1% (fused)
- Material: mixed (real material): UI screenshot
- Likely tool: After Effects / Remotion
- 93% of adjacent frames are exact duplicates, only local elements move (typical of template / motion-graphics animation, or local motion over a held frame)
- Rendered texture: flat color blocks 96%, 95% of pixels use only 1 color, horizontal / vertical straight edges 29%
- 99% of background pixels are identical frame to frame, only local elements move: 2D compositing / code-animation signature
- Re-transcoded by the platform (WeChat transcode), so sensor noise has been crushed away: noise-based evidence is void; live footage vs AI rests mainly on frame rate and picture content
- [VLM] Purple animated text on a pure white background
- [VLM] Clean 2D typographic motion with a blurred UI fading in and out
- [VLM] Background particle effect with faint colored bokeh spots
- Picture: a minimalist motion-graphics shot; light-purple text appears character by character or fades in on a white background, with pastel particles drifting, and a blurred UI screenshot briefly passes through in the middle.
- Text track (in-frame text / middle): 现在，复刻任何爆款都更简单 / 成片 / 成片也更懂你的品牌
- Remake: code rendering: rebuild from the text tracks and layout in Remotion / HTML, 100% controllable, no generative model needed; the user must supply the real material: UI screenshot (partial frame)

### #12 01:00.600–01:10.000 · Code / template rendering; introduces real material (logo / brand mark)

![shot_012](shots/shot_012.jpg)

- Probabilities: code / template rendering 89%, 3D rendering 9%, 2D animation 0% (fused)
- Material: mixed (real material): logo / brand mark
- Likely tool: After Effects
- Rendered texture: flat color blocks 65%, 95% of pixels use only 2 colors, horizontal / vertical straight edges 10%
- Re-transcoded by the platform (WeChat transcode), so sensor noise has been crushed away: noise-based evidence is void; live footage vs AI rests mainly on frame rate and picture content
- The frame has almost no color (saturation 0.01) and uses only 2 colors: a flat UI / document picture, not a 3D render with light and shadow
- [VLM] Fully flat 2D vector particle gather-and-scatter animation
- [VLM] Isometric, slanted UI layout shown in motion with a play-button interaction
- [VLM] Vector logo and typeset text fade out centered at the end, no real photographic optical traits
- Picture: on a white background, red, blue and purple speckle particles gather into a ring-shaped play button, then the camera perspective turns into a tilted UI card showcase, and finally it fades out to show the centered brand logo and text.
- Text track (in-frame text / middle): C / Oiioi视频复刻
- Text track (in-frame text / middle): 复
- Text track (in-frame text / middle): 复刻成片·品牌动效
- Remake: code rendering: rebuild from the text tracks and layout in Remotion / HTML, 100% controllable, no generative model needed; the user must supply the real material: logo / brand mark (partial frame)

## Notes

- Deterministic forensics are reliable for "is it moving, is it a whole-image push, is the texture rendered, was there a 24→30 frame-rate conversion"; telling live footage, AI and 3D apart relies on the VLM and human review.
- Platform transcoding usually strips metadata; missing metadata does not mean there was none.

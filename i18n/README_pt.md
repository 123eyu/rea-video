<div align="center">

# rea-video

Faça a engenharia reversa de qualquer vídeo.

Vídeo de apresentador, mesa de produto, vídeo de IA, 3D, motion graphics, edições mistas: mande qualquer um deles,<br>
e ele mostra, plano a plano, como foram feitos a imagem, os textos estilizados, a edição e o áudio, e depois entrega um plano para você fazer o seu.

[中文](README_zh.md) | [English](../README.md) | [Русский](README_ru.md) | [日本語](README_ja.md) | [한국어](README_ko.md) | [Español](README_es.md) | Português | [Français](README_fr.md) | [Deutsch](README_de.md)

[![Stars](https://img.shields.io/github/stars/JuneYaooo/rea-video?style=flat)](https://github.com/JuneYaooo/rea-video/stargazers)
![Python](https://img.shields.io/badge/python-%E2%89%A53.10-blue)
![Agent](https://img.shields.io/badge/runs%20in-Claude%20Code%20%7C%20Codex-8A2BE2)

<img src="../docs/cases/demo.gif" width="440" alt="Esquerda: original do TikTok gravado com celular; direita: remake com IA feito por outra pessoa, com outro produto">

Esquerda: um anúncio do TikTok gravado com celular. Direita: um remake com IA feito por outra pessoa, trocando o produto.<br>
Veredito do rea-video: o da esquerda é todo filmagem real, um cenário e duas posições de câmera; o da direita é todo gerado por IA, e seus 8 planos podem ser produzidos em 3 gerações.

</div>

> Os relatórios são gerados em chinês ou em inglês (o agente passa `--lang`). A documentação detalhada por enquanto está em chinês; o agente a lê e responde no seu idioma. Os seis relatórios de exemplo abaixo estão em inglês, para você ver como é um relatório sem instalar nada.

## O que ele consegue analisar

| Tipo de vídeo | Exemplos | O que você recebe |
|---|---|---|
| Filmagem real | Apresentador falando para a câmera, mesa de produto, demonstração de produto na mão, vlog, visita a loja | Cenários e posições de câmera, enquadramento, movimentos de câmera, iluminação (12 esquemas com lista de equipamentos), correção de cor |
| Vídeo de IA | Texto/imagem para vídeo, minissérie de IA, videoclipe de IA | Evidências, um prompt reconstruído por plano, como agrupar em gerações e qual modelo usar |
| Avatar | Um retrato animado por áudio, sincronia labial | Quais planos são de avatar, que retrato e áudio você precisa |
| 3D / animação | Vídeos explicativos em Blender / C4D, animação de produto, animação 2D, stop-motion | Se vale gerar com um modelo de vídeo ou renderizar a partir de código 3D |
| Código / template | Tipografia animada, demos de interface, gráficos, cartões estilo slide | Texto, layout e tempo das animações, prontos para recriar como projeto Remotion |
| Gravação de tela | Tutoriais de software, demos na web | Quais partes são material real que você mesmo vai precisar gravar |
| Misto / edições | Personagens de IA + interface em código + gravação de tela real; filmagem real com edições de IA | Cada plano avaliado separadamente e depois remontado na linha do tempo original |

Além de como a imagem foi feita, todo vídeo também recebe:

- Legendas e textos estilizados: início e fim de cada linha (exporta para SRT / ASS), além de cor, contorno e como o texto entra
- Figurinhas, emoji, picture-in-picture: onde ficam e por quanto tempo
- Edição: onde estão os cortes, em que ritmo, se batem com a música
- Áudio: voz humana ou de IA, música de IA ou de biblioteca e seu BPM, onde cai cada efeito sonoro
- Material que você mesmo vai fornecer: gravações de tela, capturas de tela, fotos de produto

## Primeiros passos

O rea-video foi feito para agentes de IA. No Claude Code, no Codex ou em qualquer agente que execute comandos, diga:

```text
Instale https://github.com/JuneYaooo/rea-video e depois analise este vídeo: /path/to/video.mp4
```

O agente instala a CLI, aprende o fluxo de trabalho e executa tudo. Você precisa de ffmpeg e Python 3.10+.

<details><summary>Instalação manual</summary>

```bash
brew install ffmpeg            # sudo apt install ffmpeg
git clone https://github.com/JuneYaooo/rea-video && cd rea-video
bash scripts/install_skill.sh  # instala a CLI (pip, ou pipx / .venv local) e liga o skill
rea-video --help
```

</details>

Você recebe:

- um resumo de uma linha, por exemplo "41% vídeo de IA + 59% interface em código, 8 s de gravação de tela real, música de biblioteca a 122 BPM"
- um plano de remake, dividido entre o que filmar, o que gerar e o que programar
- um `report.html` completo com quadros de cada plano, evidências, prompts, notas de câmera e iluminação e a análise do áudio

Adicione um modelo que entenda vídeo — Gemini ou Doubao funcionam: passe ao agente o endpoint e a chave. Isso deixa mais precisa a distinção entre real/IA/3D e gera um prompt reconstruído para cada plano. Sem ele, tudo continua funcionando; se o seu agente consegue ver imagens, ele mesmo confere os planos duvidosos.

## Exemplos

<table>
<tr>
<td width="50%" valign="top">
<a href="../docs/cases.md#2-混合片ai-人物对话--代码界面--真实录屏"><img src="../docs/cases/dual_role/thumb.jpg"></a><br>
<b>Clipe misto</b> · 19 s · 10 planos<br>
Personagens de IA conversando + interface feita em código + 8 s de gravação de tela real. Os 5 planos de diálogo são intercalados por trechos de interface, mas compartilham o mesmo cenário, então uma única geração cobre todos.<br>
<a href="../docs/cases/videos/dual_role.mp4">Vídeo</a> · <a href="../docs/cases/dual_role/report_en.md">Relatório</a>
</td>
<td width="50%" valign="top">
<a href="../docs/cases.md#3-3d-科普片咸鸭蛋为什么会流油"><img src="../docs/cases/salted_egg/thumb.jpg"></a><br>
<b>Explicativo em 3D</b> · 67 s · 21 planos<br>
Todo em 3D, narração por IA. Dá para fazer com 10 gerações de vídeo, ou pedir a um LLM que escreva código em Blender / Three.js.<br>
<a href="../docs/cases/videos/salted_egg.mp4">Vídeo</a> · <a href="../docs/cases/salted_egg/report_en.md">Relatório</a>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<a href="../docs/cases.md#4-代码-ui-动效产品宣传片"><img src="../docs/cases/v10/thumb.jpg"></a><br>
<b>Vídeo promocional de produto</b> · 70 s · 12 planos<br>
83% motion graphics feitos em código, 12% gravação de tela. Não precisa de modelo de vídeo; um projeto Remotion resolve.<br>
<a href="../docs/cases/videos/v10_oiioii_gen_coding_first.mp4">Vídeo</a> · <a href="../docs/cases/v10/report_en.md">Relatório</a>
</td>
<td width="50%" valign="top">
<a href="../docs/cases.md#5-ai-音乐-mv歌是-ai-写的还是曲库的"><img src="../docs/cases/qing_mv/thumb.jpg"></a><br>
<b>Videoclipe de IA</b> · 165 s · 86 planos<br>
Identifica corretamente a música como gerada por IA (foi feita com o Suno). O modelo de visão classificou alguns planos como "drama com atores reais"; o agente notou caracteres chineses inexistentes num pergaminho e os classificou como IA.<br>
<a href="../docs/cases/videos/qing_mv.mp4">Vídeo</a> · <a href="../docs/cases/qing_mv/report_en.md">Relatório</a>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<a href="../docs/cases.md#6-实拍带货沉浸式开箱"><img src="../docs/cases/unboxing/thumb.jpg"></a><br>
<b>Unboxing filmado</b> · 72 s · 29 planos<br>
Tudo filmagem real: celular num suporte de cima, um tapete, uma posição de câmera, sem narração, som ambiente mais trilha de biblioteca. Depois da recompressão da plataforma, a ferramenta offline classificou 35% como IA; a revisão do agente levou a 97% de filmagem real.<br>
<a href="../docs/cases/videos/unboxing.mp4">Vídeo</a> · <a href="../docs/cases/unboxing/report_en.md">Relatório</a>
</td>
<td width="50%" valign="top">
<a href="../docs/cases.md#7-ai-与真人混合用自己的出镜视频生成带货片"><img src="../docs/cases/ai_daihuo/thumb.jpg"></a><br>
<b>Híbrido de IA + pessoa real</b> · 58 s · 21 planos<br>
75% real (apresentadora falando para a câmera + filmagem da tela de um celular) e 25% IA: a criadora deu ao Jimeng um clipe dela mesma em frente à câmera e duas fotos do produto para gerar um trecho de venda com "pessoa real". A parte de IA foi detectada pela marca d'água do Jimeng e pelo texto embaralhado na caixa de presente.<br>
<a href="../docs/cases/videos/ai_daihuo.mp4">Vídeo</a> · <a href="../docs/cases/ai_daihuo/report_en.md">Relatório</a>
</td>
</tr>
</table>

## Remakes

Depois que o rea-video analisa um vídeo, a receita de remake do [cheap-claude-video](https://github.com/JuneYaooo/cheap-claude-video) gera uma nova versão: câmera, movimento, ritmo e transições seguem o original, e só os elementos que você escolher são trocados.
Estes resultados foram gerados com um MiniMax H3 auto-hospedado: o plano original serve de referência de movimento, e quadros-chave com os elementos trocados (gpt-image-2) definem o visual.
Abaixo estão três remakes que a OiiOii mostrou em seus artigos no WeChat. Para cada um fizemos duas versões: a mesma troca da OiiOii, e outra que também troca o personagem, o cenário e os objetos.
Cada GIF reproduz quatro versões em sincronia: original, remake da OiiOii, nosso remake, versão com elementos trocados.

<table>
<tr><td>
<b>Troca de roupa vista de cima</b> · 12 s<br>
Mesma troca: mulher → homem, três looks → roupas masculinas equivalentes. Troca de elementos: uma garota com três trajes Hanfu históricos num escritório chinês; o controle remoto vira um leque redondo.<br>
<img src="../docs/cases/remake/outfit.gif"><br>
<a href="../docs/cases/remake/outfit_compare.mp4">Vídeo comparativo em HD (com áudio)</a> · <a href="../docs/cases/remake/outfit_sheet.jpg">quadros do mesmo instante</a>
</td></tr>
<tr><td>
<b>Animação em papel / aquarela</b> · 30 s<br>
Mesma troca: nova garota de massinha como protagonista. Troca de elementos: uma raposa; floresta → recife de coral, nuvens → céu estrelado, pôr do sol → aurora.<br>
<img src="../docs/cases/remake/paper.gif"><br>
<a href="../docs/cases/remake/paper_compare.mp4">Vídeo comparativo em HD (com áudio)</a> · <a href="../docs/cases/remake/paper_sheet.jpg">quadros do mesmo instante</a>
</td></tr>
<tr><td>
<b>Vídeo de produto na mão</b> · 21 s · 11 planos<br>
Mesma troca: um produto novo original, adesivo em inglês → legenda em chinês. Troca de elementos: produto rosa, cozinha → mesa de camping, novos ingredientes.<br>
<img src="../docs/cases/remake/juicer.gif"><br>
<a href="../docs/cases/remake/juicer_compare.mp4">Vídeo comparativo em HD (com áudio)</a> · <a href="../docs/cases/remake/juicer_sheet.jpg">quadros do mesmo instante</a>
</td></tr>
</table>

Os vídeos comparativos em HD usam o áudio original. Os originais e as versões da OiiOii vêm dos artigos e são mostrados apenas para comparação.

## Precisão

Precisão na identificação de como cada plano foi feito, ponderada pela duração dos planos:

| | Conjunto de ajuste (15) | Holdout (16) | Vídeos do WeChat recodificados (10) |
|---|---|---|---|
| Só ferramentas (offline, grátis) | 98.3% | 99.6% / 98.9% | 88.6% |
| + modelo de visão (Gemini) | — | 99.6% / 99.8% | 99.6% |
| + revisão visual do agente | — | 99.6% / 99.8% | 100% |

Os dois números de holdout são holdout (9 vídeos) e holdout2 (7 vídeos).

Em arquivos originais, as ferramentas sozinhas quase sempre bastam. Vídeos baixados de plataformas foram recomprimidos, o que apaga a evidência de ruído, então é preciso uma verificação visual para voltar a passar de 99%.

A detecção de material real fica entre 97% e 99%, e os limites dos planos estão todos corretos. Números e como reproduzi-los: [eval/RESULTS.md](../eval/RESULTS.md).

## Como funciona

![Pipeline do rea-video](../docs/rea-flow_pt.svg)

1. Dividir: corta o vídeo em planos e separa o áudio em voz, música e efeitos.
2. Reunir evidências: mede os quadros (cadência de quadros, ruído do sensor, se a imagem inteira se desloca como um único plano, tags de AIGC nos metadados); olha as imagens (mãos, texto, física); escuta (BPM, tom, canto ou fala).
3. Decidir: evidências concretas, como tags de AIGC e cadência de quadros, pesam mais do que "parece que". Conflitos são sinalizados para o agente revisar visualmente.
4. Planejar o remake: agrupa os planos de acordo com o que o modelo de vídeo escolhido realmente consegue fazer, como duração máxima do clipe, suporte a múltiplos planos e quantas imagens de referência aceita.

## Perguntas frequentes

<details>
<summary>Qual a diferença para ferramentas de remake com um clique, como o Hypit?</summary>

O [Hypit](https://github.com/hypit-ai/hypit) recebe um vídeo de referência e faz um novo: o agente lê grades de quadros para entender o original, gera as imagens com os modelos que suporta (Seedance, PixVerse, MiniMax, Wan e outros) e renderiza legendas e motion graphics em HTML.

Ele não pergunta como o original foi feito. Uma fonte filmada passa pelo mesmo pipeline; ele não diz quantas câmeras foram usadas nem como foi a iluminação. O tipo de vídeo de IA que ele consegue reproduzir depende dos modelos disponíveis: sem Kling nem Veo, sem caminho dedicado para avatar ou 3D, e sem música de IA: você traz a sua. Ele se sai melhor em vídeos de apresentador, podcast e entrevista que seguem um roteiro, e pior em edições guiadas pela música, motion graphics de produto e curtas cinematográficos.

O rea-video não renderiza vídeo. Ele descobre, plano a plano, se algo foi filmado, gerado por IA ou feito em código, e então entrega um plano de filmagem, prompts ou uma abordagem em código para cada um. Para uma imitação rápida, o Hypit é mais rápido. Para entender como o original foi feito e refazê-lo gastando pouco, use o rea-video. Os dois funcionam bem juntos.

</details>

<details>
<summary>Preciso de um modelo que entenda vídeo? Quanto custa?</summary>

Não. O modo só com ferramentas é offline e grátis, e já é preciso em arquivos originais. Para vídeos recomprimidos baixados de plataformas, adicione um modelo que entenda vídeo (Gemini ou Doubao funcionam) ou use um agente que consiga ver imagens; você paga o que esse serviço cobrar. A geração automática de vídeo (capsule-cinema) faz primeiro uma simulação gratuita e só chama modelos pagos depois da sua confirmação.

</details>

<details>
<summary>Ele consegue refazer o vídeo inteiro automaticamente?</summary>

Em parte. Com o [capsule-cinema](https://github.com/JuneYaooo/cheap-claude-video) instalado, os planos de IA são gerados e colocados de volta na linha do tempo original automaticamente. Os planos reais você filma seguindo o plano de filmagem; os planos em código o agente escreve como um projeto Remotion. Veja [docs/replicate.md](../docs/replicate.md).

</details>

<details>
<summary>Posso simplesmente repostar o vídeo de outra pessoa?</summary>

Não. O rea-video serve para aprender a estrutura, o ritmo e as técnicas de um vídeo e depois refazê-lo com material sobre o qual você tem direitos. Não reutilize imagens, músicas, personagens ou a imagem de outras pessoas. Siga as regras da plataforma e as exigências locais de identificação de conteúdo gerado por IA ao publicar.

</details>

## Documentação

- [docs/what-it-detects.md](../docs/what-it-detects.md): tudo o que ele detecta (10 tipos visuais, câmera, iluminação, cor, áudio)
- [docs/replicate.md](../docs/replicate.md): como refazer a partir do relatório
- [docs/cases.md](../docs/cases.md): detalhes dos casos
- [docs/decompose.md](../docs/decompose.md): regras de detecção
- [docs/cli.md](../docs/cli.md): uso da CLI e integração com o capsule-cinema
- [rea_video/capabilities/](../rea_video/capabilities/README.md): tabelas de capacidades de modelos de vídeo / imagem / áudio, usadas para escolher modelos no plano de remake
- [eval/RESULTS.md](../eval/RESULTS.md): resultados da avaliação

Por enquanto, a documentação está em chinês.

## Comunidade

Perguntas, análises e ideias de remake: [GitHub Discussions](https://github.com/JuneYaooo/rea-video/discussions). Também conversamos no [Discord](https://discord.gg/dZj8D3GqWT). Quem fala chinês também nos encontra no [linux.do](https://linux.do/).

Quer que um vídeo seja analisado? Abra uma [issue de pedido](https://github.com/JuneYaooo/rea-video/issues/new?template=request_breakdown.yml) com o link e publicaremos o resultado como um caso.

## Créditos

Inspirado no [REA (Reverse Engineer Anything)](https://github.com/morluto/rea): partir do que se vê para chegar a como foi feito, sustentar cada afirmação com evidências e verificar medindo.

<div align="center">

# rea-video

Faites la rétro-ingénierie de n'importe quelle vidéo.

Face caméra, table top, vidéo IA, 3D, motion design, montages mixtes : donnez-lui n'importe laquelle,<br>
et il vous explique, plan par plan, comment l'image, les textes stylisés, le montage et le son ont été faits, puis vous donne un plan pour en faire une vous-même.

[中文](README_zh.md) | [English](../README.md) | [Русский](README_ru.md) | [日本語](README_ja.md) | [한국어](README_ko.md) | [Español](README_es.md) | [Português](README_pt.md) | Français | [Deutsch](README_de.md)

[![Stars](https://img.shields.io/github/stars/JuneYaooo/rea-video?style=flat)](https://github.com/JuneYaooo/rea-video/stargazers)
![Python](https://img.shields.io/badge/python-%E2%89%A53.10-blue)
![Agent](https://img.shields.io/badge/runs%20in-Claude%20Code%20%7C%20Codex-8A2BE2)

<img src="../docs/cases/demo.gif" width="440" alt="À gauche : l'original TikTok tourné au téléphone ; à droite : un remake IA réalisé par quelqu'un d'autre avec un autre produit">

À gauche : une pub TikTok tournée au téléphone. À droite : un remake IA réalisé par quelqu'un d'autre, avec un autre produit à la place.<br>
Verdict de rea-video : la vidéo de gauche est entièrement filmée, un seul décor et deux positions de caméra ; celle de droite est entièrement générée par IA, et ses 8 plans peuvent être produits en 3 générations.

</div>

> Les rapports sont générés en chinois ou en anglais (votre agent passe `--lang`). La documentation détaillée est pour l'instant en chinois ; votre agent la lit et vous répond dans votre langue. Les six exemples de rapports ci-dessous sont en anglais, pour que vous puissiez voir à quoi ressemble un rapport sans rien installer.

## Ce qu'il sait décortiquer

| Type de vidéo | Exemples | Ce que vous obtenez |
|---|---|---|
| Prise de vue réelle | Face caméra, table top, démo produit à la main, vlog, visite de boutique | Décors et positions de caméra, cadrage, mouvements de caméra, éclairage (12 configurations avec liste de matériel), étalonnage |
| Vidéo IA | Texte/image vers vidéo, mini-série IA, clip musical IA | Indices, un prompt reconstitué pour chaque plan, comment regrouper les plans en générations et quel modèle utiliser |
| Avatar | Un portrait animé par l'audio, synchronisation labiale | Quels plans sont des plans d'avatar, quel portrait et quel audio il vous faut |
| 3D / animation | Vidéos explicatives Blender / C4D, animation produit, animation 2D, stop-motion | S'il vaut mieux générer avec un modèle vidéo ou faire un rendu à partir de code 3D |
| Code / template | Typographie animée, démos d'interface, graphiques, cartons façon diapositive | Texte, mise en page et timing des animations, prêts à être reconstruits en projet Remotion |
| Enregistrement d'écran | Tutoriels logiciels, démos web | Quelles parties sont du vrai matériel que vous devrez enregistrer vous-même |
| Mixte / montages | Personnages IA + interface en code + vraie capture d'écran ; prise de vue réelle avec retouches IA | Chaque plan est jugé séparément, puis remis en place sur la timeline d'origine |

En plus de la façon dont l'image a été faite, chaque vidéo a aussi droit à :

- Sous-titres et textes stylisés : début et fin de chaque ligne (export en SRT / ASS), plus la couleur, le contour et la façon dont le texte apparaît
- Stickers, emoji, incrustations : où ils se placent et combien de temps ils restent
- Montage : où sont les coupes, à quel rythme, si elles tombent sur le temps
- Son : voix humaine ou IA, musique IA ou de bibliothèque et son BPM, où tombe chaque effet sonore
- Matériel que vous fournirez vous-même : enregistrements d'écran, captures d'écran, photos produit

## Démarrage rapide

rea-video est conçu pour les agents IA. Dans Claude Code, Codex ou tout agent capable d'exécuter des commandes, dites :

```text
Installe https://github.com/JuneYaooo/rea-video, puis décortique cette vidéo : /path/to/video.mp4
```

L'agent installe la CLI, apprend le processus et fait tout le travail. Il vous faut ffmpeg et Python 3.10+.

<details><summary>Installation manuelle</summary>

```bash
brew install ffmpeg            # sudo apt install ffmpeg
git clone https://github.com/JuneYaooo/rea-video && cd rea-video
bash scripts/install_skill.sh  # installe la CLI (pip, sinon pipx / .venv local) et lie le skill
rea-video --help
```

</details>

Vous obtenez :

- un résumé d'une ligne, par ex. « 41 % vidéo IA + 59 % interface en code, 8 s de vrai enregistrement d'écran, musique de bibliothèque à 122 BPM »
- un plan de remake, réparti entre ce qu'il faut filmer, ce qu'il faut générer et ce qu'il faut coder
- un `report.html` complet avec les images de chaque plan, les indices, les prompts, les notes de caméra et d'éclairage, et l'analyse du son

Ajoutez un modèle capable de lire la vidéo — Gemini ou Doubao conviennent tous les deux : donnez à l'agent l'endpoint et la clé. Il rend plus précis le tri entre réel, IA et 3D, et écrit un prompt reconstitué pour chaque plan. Sans modèle, l'outil fonctionne quand même ; si votre agent peut voir les images, il vérifiera lui-même les plans incertains.

## Exemples

<table>
<tr>
<td width="50%" valign="top">
<a href="../docs/cases.md#2-混合片ai-人物对话--代码界面--真实录屏"><img src="../docs/cases/dual_role/thumb.jpg"></a><br>
<b>Clip multimédia mixte</b> · 19 s · 10 plans<br>
Personnages IA qui dialoguent + interface construite en code + 8 s de vrai enregistrement d'écran. Les 5 plans de dialogue sont entrecoupés de segments d'interface mais partagent un même décor, donc une seule génération suffit.<br>
<a href="../docs/cases/videos/dual_role.mp4">Vidéo</a> · <a href="../docs/cases/dual_role/report_en.md">Rapport</a>
</td>
<td width="50%" valign="top">
<a href="../docs/cases.md#3-3d-科普片咸鸭蛋为什么会流油"><img src="../docs/cases/salted_egg/thumb.jpg"></a><br>
<b>Vidéo explicative 3D</b> · 67 s · 21 plans<br>
Entièrement en 3D, narration IA. Faisable en 10 générations vidéo, ou en faisant écrire du code Blender / Three.js par un LLM.<br>
<a href="../docs/cases/videos/salted_egg.mp4">Vidéo</a> · <a href="../docs/cases/salted_egg/report_en.md">Rapport</a>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<a href="../docs/cases.md#4-代码-ui-动效产品宣传片"><img src="../docs/cases/v10/thumb.jpg"></a><br>
<b>Vidéo promo produit</b> · 70 s · 12 plans<br>
83 % de motion design piloté par code, 12 % d'enregistrement d'écran. Aucun modèle vidéo nécessaire ; un seul projet Remotion suffit.<br>
<a href="../docs/cases/videos/v10_oiioii_gen_coding_first.mp4">Vidéo</a> · <a href="../docs/cases/v10/report_en.md">Rapport</a>
</td>
<td width="50%" valign="top">
<a href="../docs/cases.md#5-ai-音乐-mv歌是-ai-写的还是曲库的"><img src="../docs/cases/qing_mv/thumb.jpg"></a><br>
<b>Clip musical IA</b> · 165 s · 86 plans<br>
Identifie correctement la chanson comme générée par IA (elle a été faite avec Suno). Le modèle de vision a classé certains plans en « drame en prise de vue réelle » ; l'agent a repéré de faux caractères chinois sur un rouleau et les a jugés IA.<br>
<a href="../docs/cases/videos/qing_mv.mp4">Vidéo</a> · <a href="../docs/cases/qing_mv/report_en.md">Rapport</a>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<a href="../docs/cases.md#6-实拍带货沉浸式开箱"><img src="../docs/cases/unboxing/thumb.jpg"></a><br>
<b>Unboxing en prise de vue réelle</b> · 72 s · 29 plans<br>
Entièrement filmé : un téléphone fixé en plongée, un tapis, une seule position de caméra, pas de voix off, son d'ambiance plus musique de fond de bibliothèque. Après le transcodage par la plateforme, l'outil hors ligne en classait 35 % en IA ; la vérification par l'agent a ramené le résultat à 97 % de prise de vue réelle.<br>
<a href="../docs/cases/videos/unboxing.mp4">Vidéo</a> · <a href="../docs/cases/unboxing/report_en.md">Rapport</a>
</td>
<td width="50%" valign="top">
<a href="../docs/cases.md#7-ai-与真人混合用自己的出镜视频生成带货片"><img src="../docs/cases/ai_daihuo/thumb.jpg"></a><br>
<b>Hybride IA + personne réelle</b> · 58 s · 21 plans<br>
75 % réel (face caméra + écran de téléphone filmé) et 25 % IA : la créatrice a donné à Jimeng son propre clip face caméra et deux photos produit pour générer un segment produit « avec une vraie personne ». La partie IA a été repérée grâce au filigrane Jimeng et au texte illisible sur la boîte cadeau.<br>
<a href="../docs/cases/videos/ai_daihuo.mp4">Vidéo</a> · <a href="../docs/cases/ai_daihuo/report_en.md">Rapport</a>
</td>
</tr>
</table>

## Remakes

Une fois la vidéo décortiquée par rea-video, la recette de remake de [capsule-cinema](https://github.com/JuneYaooo/capsule-cinema) génère une nouvelle version : caméra, mouvements, rythme et transitions suivent l'original, seuls les éléments que vous choisissez sont remplacés.
Ces résultats ont été générés avec un MiniMax H3 auto-hébergé : le plan original sert de référence de mouvement, et des images clés avec les éléments remplacés (gpt-image-2) définissent le rendu.
Voici trois remakes qu'OiiOii a présentés dans ses articles WeChat. Pour chacun, nous avons fait deux versions : le même remplacement qu'OiiOii, et une qui remplace aussi le sujet, le décor et les accessoires.
Chaque GIF montre quatre versions en synchronisation : l'original, le remake d'OiiOii, notre remake et la version avec éléments remplacés.

<table>
<tr><td>
<b>Changement de tenue en plongée</b> · 12 s<br>
Même remplacement : femme → homme, trois tenues → tenues masculines équivalentes. Remplacement d'éléments : une jeune fille dans trois tenues Hanfu historiques, dans un cabinet d'étude chinois ; la télécommande devient un éventail rond.<br>
<img src="../docs/cases/remake/outfit.gif"><br>
<a href="../docs/cases/remake/outfit_compare.mp4">Vidéo comparative HD (avec son)</a> · <a href="../docs/cases/remake/outfit_sheet.jpg">images au même instant</a>
</td></tr>
<tr><td>
<b>Animation papier découpé / aquarelle</b> · 30 s<br>
Même remplacement : une nouvelle fille en pâte à modeler en héroïne. Remplacement d'éléments : un renard ; forêt → récif corallien, nuages → ciel étoilé, coucher de soleil → aurore boréale.<br>
<img src="../docs/cases/remake/paper.gif"><br>
<a href="../docs/cases/remake/paper_compare.mp4">Vidéo comparative HD (avec son)</a> · <a href="../docs/cases/remake/paper_sheet.jpg">images au même instant</a>
</td></tr>
<tr><td>
<b>Vidéo produit tenue à la main</b> · 21 s · 11 plans<br>
Même remplacement : un nouveau produit original, sticker en anglais → sous-titre en chinois. Remplacement d'éléments : produit rose, cuisine → table de camping, nouveaux ingrédients.<br>
<img src="../docs/cases/remake/juicer.gif"><br>
<a href="../docs/cases/remake/juicer_compare.mp4">Vidéo comparative HD (avec son)</a> · <a href="../docs/cases/remake/juicer_sheet.jpg">images au même instant</a>
</td></tr>
</table>

Les vidéos comparatives HD utilisent le son d'origine. Les originaux et les versions d'OiiOii proviennent des articles et ne sont montrés qu'à titre de comparaison.

## Précision

Précision sur la façon dont chaque plan a été fait, pondérée par la durée des plans :

| | Jeu de réglage (15) | Holdout (16) | Vidéos WeChat réencodées (10) |
|---|---|---|---|
| Outils seuls (hors ligne, gratuit) | 98,3 % | 99,6 % / 98,9 % | 88,6 % |
| + modèle de vision (Gemini) | — | 99,6 % / 99,8 % | 99,6 % |
| + vérification visuelle par l'agent | — | 99,6 % / 99,8 % | 100 % |

Les deux chiffres holdout correspondent à holdout (9 vidéos) et holdout2 (7 vidéos).

Sur les fichiers originaux, les outils seuls suffisent la plupart du temps. Les vidéos téléchargées depuis les plateformes ont été recompressées, ce qui efface les indices liés au bruit ; il faut alors une vérification visuelle pour repasser au-dessus de 99 %.

La détection des vrais assets est de 97 à 99 %, et les limites de plans sont toutes correctes. Chiffres et méthode pour les reproduire : [eval/RESULTS.md](../eval/RESULTS.md).

## Comment ça marche

![Pipeline rea-video](../docs/rea-flow_fr.svg)

1. Découper : couper la vidéo en plans et séparer le son en voix, musique et effets.
2. Rassembler les indices : mesurer les images (cadence d'images, bruit du capteur, si toute l'image se déplace comme un seul plan, tags AIGC dans les métadonnées) ; regarder les images (mains, texte, physique) ; écouter (BPM, tonalité, chant ou parole).
3. Trancher : les preuves solides comme les tags AIGC et la cadence d'images priment sur « ça ressemble à ». Les contradictions sont signalées pour que l'agent les vérifie visuellement.
4. Planifier le remake : regrouper les plans selon ce que le modèle vidéo cible sait réellement faire, comme la durée maximale d'un clip, la prise en charge du multi-plan et le nombre d'images de référence acceptées.

## FAQ

<details>
<summary>Quelle différence avec les outils de remake en un clic comme Hypit ?</summary>

[Hypit](https://github.com/hypit-ai/hypit) prend une vidéo de référence et en fait une nouvelle : l'agent lit des grilles d'images pour comprendre l'original, génère les séquences avec les modèles qu'il prend en charge (Seedance, PixVerse, MiniMax, Wan et d'autres), et fait le rendu des sous-titres et du motion design en HTML.

Il ne se demande pas comment l'original a été fait. Une source en prise de vue réelle passe par le même pipeline ; il ne vous dira pas combien de caméras ont été utilisées ni comment la scène a été éclairée. La vidéo IA qu'il peut reproduire dépend des modèles dont il dispose : pas de Kling ni de Veo, pas de filière dédiée aux avatars ou à la 3D, et pas de musique IA : vous apportez la vôtre. Il est le plus fort sur les vidéos face caméra, podcasts et interviews qui suivent un script, et plus faible sur les montages portés par la musique, le motion design produit et les courts-métrages cinématographiques.

rea-video ne fait pas le rendu d'une vidéo. Il détermine, plan par plan, si quelque chose a été filmé, généré par IA ou construit en code, puis donne pour chacun un plan de tournage, des prompts ou une approche en code. Pour une imitation rapide, Hypit est plus rapide. Pour comprendre comment l'original a été fait et le refaire à moindre coût, utilisez rea-video. Les deux s'utilisent très bien ensemble.

</details>

<details>
<summary>Ai-je besoin d'un modèle capable de lire la vidéo ? Combien ça coûte ?</summary>

Non. Le mode outils seuls fonctionne hors ligne et gratuitement, et il est déjà précis sur les fichiers originaux. Pour les vidéos recompressées téléchargées depuis les plateformes, ajoutez un modèle capable de lire la vidéo (Gemini ou Doubao conviennent tous les deux) ou utilisez un agent qui peut voir les images ; vous payez ce que facture ce service. La génération vidéo automatique (capsule-cinema) fait d'abord un essai à blanc gratuit et n'appelle les modèles payants qu'après votre confirmation.

</details>

<details>
<summary>Peut-il refaire toute la vidéo automatiquement ?</summary>

En partie. Avec [capsule-cinema](https://github.com/JuneYaooo/capsule-cinema) installé, les plans IA sont générés et replacés automatiquement sur la timeline d'origine. Les plans réels, vous les filmez d'après le plan de tournage ; les plans en code, l'agent les écrit sous forme de projet Remotion. Voir [docs/replicate.md](../docs/replicate.md).

</details>

<details>
<summary>Puis-je simplement republier la vidéo de quelqu'un d'autre ?</summary>

Non. rea-video sert à étudier la structure, le rythme et les techniques d'une vidéo, puis à la refaire avec du matériel dont vous détenez les droits. Ne réutilisez pas les séquences, la musique, les personnages ou l'image d'autres personnes. Respectez les règles des plateformes et les obligations locales d'étiquetage des contenus IA lorsque vous publiez.

</details>

## Documentation

- [docs/what-it-detects.md](../docs/what-it-detects.md) : tout ce qu'il détecte (10 types visuels, caméra, éclairage, étalonnage, son)
- [docs/replicate.md](../docs/replicate.md) : refaire une vidéo à partir du rapport
- [docs/cases.md](../docs/cases.md) : détail des cas
- [docs/decompose.md](../docs/decompose.md) : règles de détection
- [docs/cli.md](../docs/cli.md) : utilisation de la CLI et intégration de capsule-cinema
- [rea_video/capabilities/](../rea_video/capabilities/README.md) : tableaux des capacités des modèles vidéo / image / audio, utilisés pour choisir les modèles du plan de remake
- [eval/RESULTS.md](../eval/RESULTS.md) : résultats d'évaluation

La documentation est pour l'instant en chinois.

## Communauté

Questions, décorticages et idées de remake : [GitHub Discussions](https://github.com/JuneYaooo/rea-video/discussions). On discute aussi sur [Discord](https://discord.gg/dZj8D3GqWT). Les sinophones peuvent aussi nous trouver sur [linux.do](https://linux.do/).

Vous voulez faire décortiquer une vidéo ? Ouvrez une [issue de demande](https://github.com/JuneYaooo/rea-video/issues/new?template=request_breakdown.yml) avec le lien et nous publierons le résultat sous forme de cas.

## Remerciements

Inspiré par [REA (Reverse Engineer Anything)](https://github.com/morluto/rea) : remonter de ce que l'on voit à la façon dont cela a été fait, étayer chaque affirmation par des preuves, et vérifier par la mesure.

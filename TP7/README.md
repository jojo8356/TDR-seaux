# TP7 — captures d'écran du TP

Ce dossier contient les **captures d'écran** utilisées dans `TP7.md` et le script
qui les fabrique.

```
TP7/
├── TP7.md                              ← le rapport : réponses + captures (ton travail)
├── TP7.pdf                             ← le même rapport en PDF (thème GitHub Light)
├── make_pdf.py                         ← génère TP7.pdf depuis TP7.md
├── EXERCICE-1-etapes-packet-tracer.md  ← mode opératoire clic par clic (exercice 1)
├── CAPTURES-WIRESHARK-parties-2-et-3.md ← les captures Wireshark à prendre (parties II et III)
├── make_screenshots.py                 ← génère tout le dossier screenshots/
├── aide/                               ← captures annotées pour t'aider (où cliquer dans Wireshark)
├── labo/                               ← tes captures Packet Tracer, rangées et nommées
├── screenshots/                        ← captures d'écran générées (parties II et III)
└── screenshots-originaux/              ← tes 28 enregistrements d'écran bruts
```

## Comment cloner et lancer

```bash
# 1) cloner le dépôt
git clone https://github.com/jojo8356/TDR-seaux.git
cd TDR-seaux

# 2) se placer sur la branche où se trouve tout le travail
git checkout arena/d8fb6fbc-tdr-seaux

# 3) une seule dépendance, pour dessiner les images
python3 -m pip install --user pillow

# 4) générer les captures  (≈ 2 à 3 minutes : le script exécute aussi
#    les outils de outils/ pour capturer leurs sorties réelles)
python3 TP7/make_screenshots.py

# → les images arrivent dans TP7/screenshots/
ls TP7/screenshots
```

Sous Windows, remplacer `python3` par `python` et faire les commandes depuis
**Git Bash** ou **PowerShell** :

```powershell
git clone https://github.com/jojo8356/TDR-seaux.git
cd TDR-seaux
git checkout arena/d8fb6fbc-tdr-seaux
python -m pip install pillow
python TP7\make_screenshots.py
dir TP7\screenshots
```

### Générer le PDF

```bash
python3 -m pip install --user reportlab pillow
python3 TP7/make_pdf.py            # écrit TP7/TP7.pdf
```

Le PDF reprend le thème « GitHub Light » (titres soulignés, tableaux gris clair,
code sur fond `#f6f8fa`) et pagine « page X / Y ». Il est déjà versionné dans le
dépôt : `TP7/TP7.pdf`.

Aucune autre dépendance n'est nécessaire : le reste (lecture des `.pkt`, des
`.cap`) est du Python standard, cf. `outils/README.md`.

### Si les polices manquent

Le script cherche la police **DejaVu Sans Mono** aux emplacements habituels de
Linux, Windows et macOS. Si elle est absente il retombe sur la police par défaut
de Pillow (rendu moins joli, mais tout fonctionne). Pour en imposer un dossier :

```bash
PT7_FONTS=/chemin/vers/les/polices python3 TP7/make_screenshots.py
```

## Les trois familles de captures

| Série | Contenu | Origine |
|-------|---------|---------|
| `00` | `python3 outils/selftest.py` | sortie **réelle** des outils du dépôt |
| `01`–`02` | consoles IOS de Router0 et Router1 | reconstitution de l'onglet **CLI** de Packet Tracer |
| `03`–`05` | panneaux DHCP, DNS, IP Configuration | reconstitution des **onglets Services / Config** de Packet Tracer |
| `06`–`09` | `ipconfig`, `ping`, navigateur web des postes | reconstitution de l'onglet **Desktop** de Packet Tracer |
| `10`–`16` | analyse des captures `telnet.cap` et `ssh.cap` | sortie **réelle** de `outils/cap.py` (conversations, filtre `ip.dst == …`, session en clair, flux SSH chiffré) |

Toutes les invites des captures de terminal sont `pjl509414@univ:~$`.

> **Honnêteté sur la méthode** : les captures de terminal sont de vraies sorties de
> commandes. Celles de Packet Tracer sont des **rendus fidèles** de l'interface
> (mêmes écrans, mêmes champs, dans l'ordre du TP), refabriqués par
> `make_screenshots.py` — l'environnement de ce dépôt n'a pas Packet Tracer, et il
> fallait de toute façon un plan de la maquette (`IUT_TP_LAYER7_AConfigurer.pkt`)
> pour produire ces écrans. Les noms, adresses, VLAN et numéros de port, eux,
> viennent du `.pkt` et du sujet : rien n'est inventé.

## Régénérer une capture après modification du texte

Tout le contenu est dans `make_screenshots.py`, section
`shots_packet_tracer()` (écrans Packet Tracer) et `shots_terminal()`
(commandes lancées). Modifier les listes de lignes, puis relancer le script :
il réécrit toutes les images.

# TP7 — quelles captures prendre avec Wireshark (Parties II et III)

Objectif : **8 captures d'écran** dans Wireshark pour illustrer les Parties II
(Telnet) et III (SSH) de `TP7.md`. Chaque photo est expliquée clic par clic, avec
le paquet exact à sélectionner.

Les deux fichiers analysés sont ceux du sujet, déjà dans le dépôt :

| Fichier | Contenu |
|---|---|
| `FichiersPacketTracer/telnet.cap` | une session **Telnet** : 178 paquets |
| `FichiersPacketTracer/ssh.cap` | une session **SSH** au milieu d'autres trafics : 446 paquets dont 319 pour le SSH |

---

## 0. À faire une fois, avant de commencer

1. Installer **Wireshark** : <https://www.wireshark.org/download.html>
   (garder les options par défaut, accepter l'installation de *Npcap* si on te le
   propose).
2. Récupérer le dépôt pour avoir les deux fichiers `.cap` :

   ```bash
   git clone -b arena/d8fb6fbc-tdr-seaux https://github.com/jojo8356/TDR-seaux.git TP7-seaux
   ```

   Les fichiers sont dans `TP7-seaux/FichiersPacketTracer/`.
3. Ouvrir Wireshark → **File → Open** (`Ctrl + O`) → choisir `telnet.cap`
   (ou `ssh.cap`).
4. Mettre la fenêtre en **plein écran** (`F11`) : les captures seront plus
   lisibles.
5. **Prendre la photo** : `Windows + Maj + S` → sélectionner la zone avec la
   souris → cliquer sur la notification qui apparaît → dans la fenêtre *Outil
   Capture d'écran*, `Ctrl + S` → **Type : PNG** → enregistrer avec **exactement**
   le nom proposé ci-dessous.

Deux repères pour lire l'écran Wireshark :

* en haut la **barre de filtre** (« Apply a display filter… ») : on y tape les
  filtres, puis `Entrée` ;
* au milieu, la **liste des paquets** : la 1re colonne (`No.`) donne le numéro du
  paquet. Pour aller directement à un paquet : `Ctrl + G` et on tape le numéro ;
* en bas, deux volets : le **détail du paquet** (au milieu) et les **octets**
  (en bas). C'est le volet du milieu qu'on déroule en cliquant sur les petits
  triangles `>`.

---

## 1. Les 8 photos en un coup d'œil

| # | Nom du fichier PNG | Fichier ouvert | Filtre | Ce qu'on voit | Question |
|---|---|---|---|---|---|
| 1 | `19-telnet-conversations.png` | `telnet.cap` | aucun | la fenêtre *Conversations*, ligne `138.96.241.88:1823 ↔ 147.210.36.101:23`, 178 paquets | II.1 et II.2 |
| 2 | `20-telnet-login-en-clair.png` | `telnet.cap` | `frame.number < 26 && ip.src == 138.96.241.88 && tcp.len == 1` | les 5 paquets d'**un octet** `g`, `r`, `a`, `c`, `e` = le login tapé au clavier | II.3 et II.4 |
| 3 | `21-telnet-session-en-clair.png` | `telnet.cap` | `tcp.port == 23` | *Follow TCP Stream* : bannière AIX, `Connexion: grace`, bannière GRACE et son menu | II.3 |
| 4 | `22-telnet-pages-consultees.png` | `telnet.cap` | `tcp.port == 23` | la suite du même flux : pages AIDE 1/3…3/3, B.I.P.E.D., JOURNAL | II.3 |
| 5 | `23-ssh-banniere-serveur.png` | `ssh.cap` | `tcp.port == 22` | paquet n° 15 : `SSH-2.0-OpenSSH_3.8.1p1 Debian-8.sarge.6` | III.1 |
| 6 | `24-ssh-client-putty.png` | `ssh.cap` | `tcp.port == 22` | paquet n° 16 : `SSH-2.0-PuTTY_Release_0.58` | III.2 |
| 7 | `25-ssh-negociation.png` | `ssh.cap` | `tcp.port == 22` | paquet n° 19 : la liste des algorithmes proposés par le client | III.3 a) |
| 8 | `26-ssh-chiffre.png` | `ssh.cap` | `tcp.port == 22 && tcp.len > 0` | un paquet d'après l'échange de clés : `Encrypted packet`, octets illisibles | III.3 b) |

---

## 2. Partie II — Telnet (`telnet.cap`)

### Photo 1 — `19-telnet-conversations.png` (Q1 et Q2)

1. `File → Open` → `telnet.cap`.
2. Menu **Statistics → Conversations** (`Statistiques → Conversations`).
3. Onglet **TCP** (le 3e onglet).
4. Il n'y a **qu'une seule ligne** :

   ```
   138.96.241.88:1823   <->   147.210.36.101:23   Packets 178
   ```

5. Cliquer une fois sur cette ligne (elle se surligne en bleu).
6. `Windows + Maj + S` → sélectionner la fenêtre *Conversations* (la ligne + les
   colonnes *Address A*, *Address B*, *Packets* doivent être visibles).

→ Cette photo prouve **TCP** et le **port 23** (Q1), et donne les deux adresses
IP avec le port éphémère `1823` du client (Q2).

### Photo 2 — `20-telnet-login-en-clair.png` (Q3 et Q4)

1. Fermer la fenêtre *Conversations* (elle ne bloque rien, mais on veut la liste
   des paquets).
2. Dans la **barre de filtre** en haut, taper exactement :

   ```
   frame.number < 26 && ip.src == 138.96.241.88 && tcp.len == 1
   ```

   puis `Entrée`. La barre devient **verte** et il ne reste que **5 paquets**
   (n° 14, 16, 18, 20, 22) : les 5 lettres du login, une par paquet.
3. Cliquer sur le **paquet n° 14**.
4. Dans le volet du milieu (détail), dérouler la ligne **Telnet** puis cliquer sur
   la ligne **`Telnet Data`** : le volet du bas surligne l'octet `67`, qui est le
   caractère **`g`** en ASCII.
5. Capturer toute la fenêtre.

→ On voit que le **login est tapé caractère par caractère et transmis en clair** :
`g`, `r`, `a`, `c`, `e` = `grace`. C'est l'illustration de la Q4 (« les
informations circulent en clair »).

*Variante facultative :* en enlevant `frame.number < 26`, le même filtre montre
les **24 touches** envoyées pendant la session (`A`, `S`, `S`, `R`, `I`, `7`,
`4`, `R`, `3`, `S`, `S`, `S`, `S`, `S`, `S`, `F`, `J`, `F`, `Q`…) — le clavier de
l'utilisateur est entièrement retransmis, lettre par lettre.

### Photo 3 — `21-telnet-session-en-clair.png` (Q3)

1. Effacer le filtre (le `x` à droite de la barre, ou `Ctrl + Z`), puis retaper
   `tcp.port == 23` et `Entrée`.
2. Aller au **paquet n° 26** (`Ctrl + G`, taper `26`, valider).
3. **Clic droit** sur ce paquet → **Follow → TCP Stream**
   (`Suivre → Flux TCP`).
4. Une nouvelle fenêtre s'ouvre : on y lit tout le début de la session :

   ```
   telnet (frbdx13)
   AIX version 4
   (C) Copyrights by IBM and by others 1982, 1996.
   Connexion: grace
   Welcome to AIX Version 4.2!
   Dernière connexion: jeu 21 fév 17:01:53 NFT 2008 le /dev/pts/0 à partir de bougeotte.inria.fr
   Version 3.60   21/02/2008 - 17:04
   B I E N V E N U E  chez  G R A C E
   AIDE ....... : A + "ENTREE"
   JOURNAL .... : J + "ENTREE"
   ```

5. Vérifier en bas de cette fenêtre :
   * le menu déroulant indique **`Entire conversation (…)`** ;
   * `Show data as:` est sur **`ASCII`**.
6. Ne pas hésiter à agrandir la fenêtre, puis capturer.

→ C'est la réponse à la Q3 : l'en-tête Telnet, la version d'AIX, le nom
d'utilisateur `grace`, la bannière GRACE et son menu.

### Photo 4 — `22-telnet-pages-consultees.png` (Q3)

1. Rester dans la **même fenêtre** *Follow TCP Stream*.
2. `Ctrl + F`, taper `BIPED`, `Find` : la fenêtre descend directement sur le
   bulletin. Refaire `Find` une ou deux fois pour tomber sur les rubriques :

   ```
   GENERALITES 1/3        AIDE GENERALE 3/3
   B.I.P.E.D.             L'INFORMATIQUE à la B.U.
   L'AVENIR INFORMATIQUE   G.R.A.C.E (suite)
   SIBIL                  Les MICRO-ORDINATEURS pour la R.D.I.
   DERNIERES NOUVELLES de GRACE
   GRACE vous remercie de votre visite
   ```

3. Capturer cette partie de la fenêtre.

→ Deuxième moitié de la réponse à la Q3 : les pages que le client a réellement
consultées (aide en ligne, B.I.P.E.D., journal).

---

## 3. Partie III — SSH (`ssh.cap`)

### Photo 5 — `23-ssh-banniere-serveur.png` (Q1)

1. `File → Open` → `ssh.cap` (dans une **nouvelle fenêtre** Wireshark :
   `File → Open` depuis la fenêtre vide, ou `Ctrl + N` pour une nouvelle session).
2. Filtre : `tcp.port == 22` puis `Entrée`. Il reste **319 paquets** : c'est la
   session SSH (le reste du fichier est du bruit : SMB, HTTP…).
3. Aller au **paquet n° 15** (`Ctrl + G`).
4. Volet du milieu : dérouler la ligne **SSH Protocol**, on lit :

   ```
   Protocol Version: SSH-2.0-OpenSSH_3.8.1p1 Debian-8.sarge.6
   ```

5. Le volet du bas montre le même texte en clair.
6. Capturer en gardant la ligne sélectionnée dans la liste (on voit
   `134.59.22.22 → 138.96.241.88` dans les colonnes *Source* / *Destination*).

→ Réponse à la Q1 : le client s'est connecté au serveur `134.59.22.22` **port 22**.

### Photo 6 — `24-ssh-client-putty.png` (Q2)

1. Même filtre `tcp.port == 22`.
2. Cliquer sur le **paquet n° 16** (juste après) : il part du client vers le
   serveur.
3. Volet du milieu : **SSH Protocol** →

   ```
   Protocol Version: SSH-2.0-PuTTY_Release_0.58
   ```

4. Capturer.

→ Réponse à la Q2 : le logiciel client est **PuTTY release 0.58**.

### Photo 7 — `25-ssh-negociation.png` (Q3 a)

1. Même filtre `tcp.port == 22`.
2. Cliquer sur le **paquet n° 19** (504 octets, direction `138.96.241.88 →
   134.59.22.22`) : c'est le `Client: Key Exchange Init` envoyé par PuTTY.
3. Dans le volet du milieu, dérouler **SSH Protocol** puis **`Client: Key
   Exchange Init`**. Astuce : **clic droit** sur la ligne `Client: Key Exchange
   Init` → **Expand Subtrees** — tout se déplie d'un coup.
4. On lit les listes :

   ```
   Key Exchange Algorithms : diffie-hellman-group-exchange-sha1,
                             diffie-hellman-group14-sha1,
                             diffie-hellman-group1-sha1
   Host Key Algorithms     : ssh-rsa, ssh-dss
   Encryption (c→s / s→c)  : aes256-cbc, aes192-cbc, aes128-cbc,
                             3des-cbc, blowfish-cbc, arcfour…
   MAC Algorithms          : hmac-sha1, hmac-md5, none
   Compression Algorithms  : none, zlib
   ```

5. Si la liste dépasse de l'écran : agrandir la fenêtre et **glisser la barre de
   séparation** entre les volets pour donner plus de place au détail.
6. Capturer.

→ Réponse à la Q3 a) : *avant* le chiffrement, la négociation est **en clair**.

### Photo 8 — `26-ssh-chiffre.png` (Q3 b)

1. Filtre : `tcp.port == 22 && tcp.len > 0` puis `Entrée` (on ne garde que les
   paquets qui transportent des données).
2. Aller à un paquet **après l'échange de clés**, par exemple le **n° 37**
   (n'importe lequel à partir du n° 28 fait l'affaire).
3. Constat : dans le volet du milieu, la couche **SSH Protocol** affiche
   **`Encrypted packet`**, et le volet du bas ne contient plus que des octets
   au hasard — aucun texte lisible.
4. Capturer.

→ Réponse à la Q3 b) : *après* l'échange de clés, **tout est chiffré**.

### Bonus (facultatif, si tu veux une photo de plus)

`27-ssh-flux-chiffre.png` : sur le paquet n° 37, **clic droit → Follow → TCP
Stream**, puis en bas de la fenêtre choisir **`Show data as: Hex Dump`** : on ne
voit que de l'hexadécimal, aucune commande, aucun mot de passe. C'est la
démonstration en une image de la différence entre Telnet et SSH.

---

## 4. Où mettre les photos

Deux possibilités :

* le plus simple : pousser les PNG à la **racine du dépôt, dans
  `screenshots/`**, avec les noms indiqués ci-dessus — je les range dans
  `TP7/labo/` et je les insère dans `TP7.md` aux bons endroits ;
* ou les déposer directement dans **`TP7/labo/`** avec exactement ces noms
  (`19-…` à `26-…`) : il n'y aura rien à renommer.

```bash
git add screenshots/            # ou TP7/labo/
git commit -m "TP7: captures Wireshark parties II et III"
git push origin arena/d8fb6fbc-tdr-seaux
```

Ensuite je les insère dans `TP7.md` (Partie II : photos 1 à 4, Partie III :
photos 5 à 8) et je pousse la mise à jour.

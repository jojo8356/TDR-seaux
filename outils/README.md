# Outils Packet Tracer en ligne de commande

Boîte à outils pour **lire, inspecter et réécrire les fichiers `.pkt` / `.pka` et les
captures `.cap` du TP**, directement dans le terminal, sans Packet Tracer et sans
installation (Python 3.8+ standard, aucune dépendance externe).

Tout a été testé sur les fichiers de ce dépôt, y compris le **ré-encodage identique
octet pour octet** au fichier d'origine.

---

## 1. Utilisation rapide

```bash
# Vérifier que tout fonctionne sur les fichiers du dépôt
python3 outils/selftest.py

# Voir le contenu d'une maquette : équipements, modèles, ports, IP, configs
python3 outils/pkt.py devices FichiersPacketTracer/IUT_TP_LAYER7_AConfigurer.pkt

# Extraire les running-config / startup-config (affichage ou dossier)
python3 outils/pkt.py configs FichiersPacketTracer/IUT_TP_LAYER7_AConfigurer.pkt --running-only
python3 outils/pkt.py configs FichiersPacketTracer/IUT_TP_LAYER7_AConfigurer.pkt -o configs/

# .pkt -> XML lisible (1,4 Mo pour le TP), et retour XML -> .pkt
python3 outils/pkt.py decode FichiersPacketTracer/IUT_TP_LAYER7_AConfigurer.pkt -o tp7.xml
python3 outils/pkt.py encode tp7.xml -o tp7_modifie.pkt

# Modifier un fichier : remplacer du texte dans le XML et réécrire un .pkt valide
python3 outils/pkt.py edit maquette.pkt --replace "<LINE>hostname Switch</LINE>" \
                           --with "<LINE>hostname Switch-TEST</LINE>" -o maquette2.pkt

# Contrôle d'intégrité : tag cryptographique + aller-retour du fichier
python3 outils/pkt.py check FichiersPacketTracer/IUT_TP_LAYER7_AConfigurer.pkt

# Captures réseau
python3 outils/cap.py flows  FichiersPacketTracer/telnet.cap
python3 outils/cap.py text   FichiersPacketTracer/telnet.cap
python3 outils/cap.py follow FichiersPacketTracer/telnet.cap \
        --client 138.96.241.88:1823 --server 147.210.36.101:23
```

### Exemple de sortie (`pkt.py check`)

```
Fichier    : FichiersPacketTracer/IUT_TP_LAYER7_AConfigurer.pkt (126471 octets)
Tag EAX    : valide (le fichier est authentique et non corrompu)
XML        : 1473934 octets — <PACKETTRACER5>
Ré-encodage: identique octet pour octet à l'original
Aller-retour XML : OK
```

### Exemple de sortie (`pkt.py devices`)

```
Version Packet Tracer : 8.2.2.0400
11 équipement(s) :

  NOM              TYPE           MODÈLE                 PORT   IP / CONFIG
  Laptop0          Laptop         Laptop-PT              4      169.254.172.179
  PC0              Pc             PC-PT                  4      169.254.20.48
  Switch0          Switch         2950-24                24     -  [config running]
  Router0          Router         1841                   2      -  [config running]
  Server0          Server         Server-PT              2      -
  Switch1          Switch         2950-24                24     -  [config running]
  Router1          Router         1941                   2      -  [config running]
  ...
```

---

## 2. Pourquoi c'est possible : le format `.pkt`

Un `.pkt` / `.pka` est un **XML** (topologie, adresses, running-config, annotations,
images du fond de plan…) qui a subi quatre transformations réversibles :

| # | Transformation | Sens inverse |
|---|----------------|--------------|
| 1 | compression **zlib** précédée de la taille décompressée (4 octets, big-endian) — format « qCompress » de Qt | `zlib.decompress` |
| 2 | **XOR positionnel** : `b[i] ^= (len − i) & 0xFF` | identique (XOR) |
| 3 | chiffrement **Twofish-EAX** (clé `0x89` ×16, nonce `0x10` ×16, tag d'authentification de 16 octets) | EAX / CTR |
| 4 | XOR positionnel + **inversion** : `out[len−1−i] = in[i] ^ ((len − i·len) & 0xFF)` | identique |

Ces quatre étapes sont implémentées dans `pkt.py` (`decode_bytes` / `encode_bytes`).
La clé et le nonce sont **constants** : ce n'est pas un secret, seulement une
obfuscation d'enveloppe. Le tag EAX sert de somme de contrôle : un fichier tronqué
ou modifié à la main hors de l'outil est détecté.

Chiffrement par bloc : `twofish.py`, implémentation pure Python de B. Edstrom
(dérivée de celle de B. Gladman, usage libre avec mention de l'origine — l'entête
d'origine est conservée). Le mode EAX (CMAC + CTR) est réécrit dans `pkt.py`.

> Les anciens outils (2014) ne connaissaient que l'étape 2 (XOR avec la taille du
> fichier) et **échouent sur Packet Tracer ≥ 7** : c'est le cas du fichier de ce TP
> (version 8.2.2.0400).

---

## 3. Ce que cela donne sur ce TP

* **Topologie** : 4 postes, 2 switchs 2950-24, 2 routeurs (1841 et 1941), 1 serveur.
  `Switch0` porte les VLAN 10 et 20 (`FastEthernet0/1` à `0/4` en accès, `0/5` en
  trunk) ; `Router0` (1841) a déjà les sous-interfaces `FastEthernet0/0.10` et
  `.20` mais **sans adresse IP** — c'est ce que le TP demande de compléter, avec le
  `ip helper-address 172.16.24.12` pour les baux DHCP inter-VLAN.
* **`telnet.cap`** : une seule conversation TCP, client `138.96.241.88:1823` vers le
  serveur `147.210.36.101:23`. Tout est **en clair** : identifiant `grace`, bannière
  AIX 4.2, menu de l'application documentaire GRACE, et les touches tapées par le
  client (`A`, `S`, `R`, `I`, `J`, `F`, `Q`… = navigation dans l'aide puis
  « Q » pour quitter). `cap.py telnet_strip` retire les négociations Telnet (octets
  `0xFF`) et `ansi_strip` les codes couleur VT100, ce qui rend la session lisible.
* **`ssh.cap`** : le client est **PuTTY Release 0.58** (chaîne d'identification
  `SSH-2.0-PuTTY_Release_0.58`), le serveur `134.59.22.22:22`
  (`SSH-2.0-OpenSSH_3.8.1p1 Debian-8.sarge.6`). Seule la **négociation** est lisible
  (versions, algorithmes de chiffrement) : ensuite tout est chiffré, contrairement
  à Telnet — la capture contient aussi un `GET /aum.crl` d'Adobe Update Manager.

---

## 4. Écosystème : ce qui existe (recherche d'octobre 2026)

### Python

| Projet | Licence | État | Remarques |
|--------|---------|------|-----------|
| [axcheron/ptexplorer](https://github.com/axcheron/ptexplorer) | MIT | ancien | XOR seul → **ne marche pas** au-delà de PT 6 |
| [mircoDZ/pka2xml](https://github.com/mircodz/pka2xml) | — | référence historique | a documenté le pipeline complet |
| [Punkcake21/Unpacket](https://github.com/Punkcake21/Unpacket) | MIT | **testé OK** | pur Python sans dépendance, `unpacket.py` + `repacket.py` |
| [jeamxn/cisco-pka-to-xml](https://github.com/jeamxn/cisco-pka-to-xml) | MIT | **testé OK** | PT 7/8/9, Twofish en C compilé à la volée : décodage en 0,12 s |
| [Schryzon/pktforge](https://github.com/Schryzon/pktforge) | MIT | **testé OK** | décompilation + édition des « challenge notes » |
| [AlexSvobo/tracketpacin](https://github.com/AlexSvobo/tracketpacin) | — | générateur | fabrique des TP aléatoires (IP/VLAN variables) |
| CiscoPacketTracer-AIgrader | GNU GPL v3 | correction auto | décodage + notation d'activités par LLM |
| PyPI | — | — | **aucun paquet `packet-tracer` / `pkt` officiel** : le paquet `pkt` de PyPI est un analyseur de protocoles sans rapport ; `pip install twofish` ou `pycryptodome` ne servent qu'à accélérer le bloc de chiffrement |

Les trois projets marqués « testé OK » ont été clonés et exécutés sur
`IUT_TP_LAYER7_AConfigurer.pkt` : Unpacket, cisco-pka-to-xml et pktforge produisent
le même XML (1 473 934 octets une fois l'indentation normalisée), et le `.pkt`
ré-écrit se recharge sans perte.

### npm / Node.js

Il n'existe **aucun décodeur `.pkt` écrit en JavaScript** sur npm, mais plusieurs
paquets récents (2026) savent produire ou piloter des maquettes depuis le terminal :

| Paquet npm | Version | Ce qu'il fait |
|------------|---------|----------------|
| [`packet-tracer-skill`](https://www.npmjs.com/package/packet-tracer-skill) | 0.3.2 (sept. 2026, MIT) | génère et édite des `.pkt` pour Packet Tracer 9 par « donor lab » (on part d'une maquette modèle). Il **embarque un codec Python complet** (`scripts/vendor/twofish.py`, `twofish_pure.py`, `pkt_codec.py`) : **vérifié ici**, il décode `IUT_TP_LAYER7_AConfigurer.pkt` en un XML *identique octet pour octet* au nôtre (4ᵉ implémentation indépendante concordante) |
| [`packet-tracer-mcp`](https://www.npmjs.com/package/packet-tracer-mcp) | 0.1.1 | serveur MCP : une extension se branche dans PT 9, ouvre un pont HTTP local, et un LLM peut créer/modifier la topologie en direct |
| [`packetsmith`](https://www.npmjs.com/package/packetsmith) | 0.3.3 | agent en terminal (TUI) : « 3 routeurs en OSPF avec un LAN chacun » → la topologie se construit dans PT |
| [`md2pkt`](https://www.npmjs.com/package/md2pkt) | 0.1.2 | consignes Markdown/PDF → `.pkt`, via un pont local (port 54321) |

Ces trois derniers fonctionnent **en direct dans Packet Tracer** : le JavaScript de PT
(PTBuilder, Extensions → Scripting) tourne *dans* l'application, pas dans Node — il
faut donc Packet Tracer installé, lancé, et un pont ouvert. Ce n'est pas une solution
« hors ligne » comme notre `pkt.py`.

Pour les captures, l'écosystème Node est complet — **testé** : `pcap-parser`
(`npm i pcap-parser`) lit `telnet.cap` (178 paquets) et `ssh.cap` (446 paquets) ;
voir aussi `pcap` (bindings libpcap) et `cap`. Un paquet `twofish` existe aussi sur
npm : un décodeur `.pkt` en JavaScript serait donc possible, mais **rien de prêt à
l'emploi**.

**Conclusion** : pour manipuler les `.pkt` hors ligne, c'est le côté **Python** qui
est mature (et c'est lui que les outils npm embarquent…) ; Node.js n'apporte quelque
chose que pour l'analyse des `.cap`, ou pour piloter Packet Tracer en direct.

---

## 5. Précautions

* Le XML décodé est le **format interne** de Packet Tracer : gardez toujours une
  copie du fichier d'origine avant d'écrire, et rouvrez le `.pkt` produit dans
  Packet Tracer pour vérifier.
* Ces outils servent à **inspecter ses propres fichiers** (comprendre une maquette,
  vérifier une config, faire un `git diff` d'une topologie, comparer deux versions).
  Ils ne doivent pas servir à contourner la notation d'une activité (`.pka`) ni à
  lire des fichiers qui ne sont pas les vôtres.
* `twofish.py` conserve son entête de licence d'origine (B. Edstrom / B. Gladman :
  usage libre, mention de l'origine requise). `pkt.py`, `cap.py` et `selftest.py`
  sont sous licence MIT.

## 6. Fichiers

| Fichier | Rôle |
|---------|------|
| `pkt.py` | codec `.pkt`/`.pka` (décodage, ré-encodage, inspection, édition) |
| `twofish.py` | chiffrement Twofish pur Python (module tiers, entête d'origine conservée) |
| `cap.py` | lecture des `.cap`/`.pcap` : conversations, flux TCP, texte appliqué |
| `selftest.py` | vérifie tous les outils sur les fichiers du dépôt |

---

## 7. Aller plus loin : le TP7 rédigé

Le dossier [`TP7/`](../TP7/) contient un exemple complet d'utilisation de ces
outils : `TP7/TP7.md` répond aux questions du TP « Applications » (DHCP, HTTP, DNS,
Telnet, SSH) avec 17 captures d'écran, dont certaines sont de **vraies sorties** de
`pkt.py` et `cap.py` exécutées sous `pjl509414@univ:~$`.

```bash
python3 TP7/make_screenshots.py     # régénère toutes les captures (pip install pillow)
```

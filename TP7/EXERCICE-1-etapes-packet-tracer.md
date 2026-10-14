# Exercice 1 — mode opératoire complet dans Cisco Packet Tracer

*Partie I du TP7 « Applications » : DHCP, HTTP, DNS — toutes les étapes, de
l'ouverture du fichier jusqu'aux captures d'écran.*

**Auteur : `pjl509414@univ`** · durée indicative : **45 à 60 min** · version
Packet Tracer utilisée : **8.2.2** (l'interface est identique en 7.x et 9.x)

> Ce document dit **quoi cliquer**, **quoi taper** et, à chaque fois,
> **quelle capture d'écran prendre et sous quel nom**. Les noms de fichiers sont
> ceux utilisés par `TP7.md` : si vous les remplacez dans `TP7/screenshots/` en
> gardant les mêmes noms, le rapport continue de fonctionner sans le modifier.

---

## Récapitulatif : les 12 captures de l'exercice 1

| # | Nom du fichier | Ce que la capture doit montrer | Étape |
|---|----------------|-------------------------------|-------|
| 1 | `00b-topologie.png` | la topologie complète, tous voyants **verts** | §1 |
| 2 | `01-router0-cli.png` | console de Router0 : sous-interfaces + `show ip interface brief` | §3 |
| 3 | `02-router1-cli.png` | console de Router1 : Gig0/0, Gig0/1 + `show ip route` | §4 |
| 4 | `03-dhcp-pools.png` | *Services → DHCP* de Server0 avec les **3 pools** | §5 |
| 5 | `04-dns-records.png` | *Services → DNS* avec les **2 A Record** | §7 |
| 6 | `04b-http-servers.png` | *Services → HTTP* des deux serveurs web | §8 |
| 7 | `05-pc0-ipconfig.png` | *Desktop → IP Configuration* de PC0 en **DHCP** | §9 |
| 8 | `06-pc0-ping.png` | `ipconfig /all` + les 3 `ping` depuis PC0 | §10 |
| 9 | `07-laptop0-ping.png` | idem depuis Laptop0 (VLAN 10) | §10 |
| 10 | `08-pc0-web.png` | navigateur de PC0 sur `http://www.carrillo.edu` | §11 |
| 11 | `09-dns-verify.png` | `ping www.carrillo.edu` et `ping www.international.com` | §12 |
| 12 | `09b-dhcp-dora.png` | mode **Simulation** : les 4 messages DHCP | §13 |

*(deux captures en plus, très utiles pour la question « Que devez-vous changer au
niveau du serveur DHCP ? » : `09c-dhcp-sans-dns.png` et `09d-separation.png`, §14.)*

**Comment prendre une capture :** `Windows + Maj + S` (Capture d'écran, mode
*fenêtre*) ou `Alt + Impr. écran`, puis coller dans Paint et **Enregistrer sous →
PNG** avec le nom exact du tableau. Mac : `Cmd + Maj + 4` puis Espace pour la
fenêtre. **Redimensionnez la fenêtre Packet Tracer** pour que l'écran utile soit
bien lisible (zoom : `Ctrl + molette`).

---

## 1. Préparer le fichier de travail

1. Lancer Packet Tracer, puis **`File → Open…`** (`Ctrl + O`) et ouvrir
   `FichiersPacketTracer/IUT_TP_LAYER7_AConfigurer.pkt`.
2. **`File → Save As…`** (`Ctrl + Maj + S`) et enregistrer sous
   `TP7_Application_EX1_<votrenom>.pkt` : on travaille sur une copie, l'original
   reste intact.
3. Vérifier l'**alimentation** de tous les équipements :
   * cliquer sur `Power Distribution Device0` puis `Device1` → onglet
     **Physical** → l'interrupteur doit être sur **On** ;
   * pour chaque portable (`Laptop0`, `Laptop1`, `Laptop2`) et le PC : onglet
     **Physical** → la LED d'alimentation doit être **verte**. Sinon, cliquer sur
     l'interrupteur de la machine.
   * Astuce : `Alt + F` (**Fast Forward Time**) accélère la simulation de
     plusieurs minutes en quelques secondes — indispensable après chaque
     changement, pour laisser le temps aux voyants de passer au vert et à STP de
     se stabiliser.
4. Attendre que **tous les triangles soient verts** sur le schéma.

> 📸 **Capture `00b-topologie.png`** — la vue *Logical* complète (zoom pour voir
> les étiquettes des 4 postes, des 2 switchs, des 2 routeurs et de Server0), tous
> les liens **verts**.

---

## 2. Relever l'existant (avant de toucher à quoi que ce soit)

C'est le moment de comprendre la maquette : onglet **CLI** du `Switch0`, touche
`Entrée`, puis :

```text
Switch>enable
Switch#show vlan brief
Switch#show interfaces trunk
```

Vous devez voir : `VLAN 10` et `VLAN 20` actifs, les ports `Fa0/1` à `Fa0/4`
affectés aux VLAN, et **`Fa0/5` en mode trunk**. Idem sur `Switch1` (qui, lui, n'a
pas de VLAN : il relie le routeur et les serveurs).

Côté `Router0`, on voit les sous-interfaces déjà créées mais vides :

```text
Router>enable
Router#show ip interface brief
```

→ `FastEthernet0/0.10` et `FastEthernet0/0.20` apparaissent en `unassigned`. C'est
normal : c'est ce qu'on va remplir.

---

## 3. Router0 : sous-interfaces VLAN + relais DHCP

Cliquer sur **`Router0` → onglet `CLI`**, appuyer sur `Entrée`, puis saisir :

```text
enable
configure terminal
interface FastEthernet0/0
 no shutdown
 exit
interface FastEthernet0/0.10
 description Passerelle VLAN 10
 encapsulation dot1Q 10
 ip address 192.168.10.1 255.255.255.0
 ip helper-address 172.16.24.12
 exit
interface FastEthernet0/0.20
 description Passerelle VLAN 20
 encapsulation dot1Q 20
 ip address 192.168.20.1 255.255.255.0
 ip helper-address 172.16.24.12
 exit
ip routing
ip route 172.16.24.0 255.255.0.0 10.6.8.2
interface FastEthernet0/1
 description Vers Router1 Gig0/0 (WAN 10.6.8.0/30)
 ip address 10.6.8.1 255.255.255.252
 no shutdown
 end
show ip interface brief
```

> **Les deux lignes à ne pas oublier** : `ip helper-address 172.16.24.12` sur
> *chaque* sous-interface (c'est le relais des requêtes DHCP en broadcast vers le
> serveur) et `ip routing` (sans lui, le routeur 1841 ne route pas entre ses
> sous-interfaces).

> 📸 **Capture `01-router0-cli.png`** — la console avec les commandes **et** la
> sortie de `show ip interface brief` : `Fa0/0.10 = 192.168.10.1`,
> `Fa0/0.20 = 192.168.20.1`, `Fa0/1 = 10.6.8.1`, statut `up/up`.

---

## 4. Router1 : LAN des serveurs + route par défaut

⚠️ **Attention au câblage réel** (vérifié dans le fichier) : c'est
**`Gig0/0`** qui va vers `Router0` (WAN) et **`Gig0/1`** qui va vers `Switch1`
(LAN des serveurs). Sur `Router1` → **CLI** :

```text
enable
configure terminal
interface GigabitEthernet0/0
 description Vers Router0 Fa0/1 (WAN 10.6.8.0/30)
 ip address 10.6.8.2 255.255.255.252
 no shutdown
 exit
interface GigabitEthernet0/1
 description LAN des serveurs 172.16.24.0/16
 ip address 172.16.24.1 255.255.0.0
 no shutdown
 exit
ip route 0.0.0.0 0.0.0.0 10.6.8.1
end
show ip route
```

Attendu :

```text
Gateway of last resort is 10.6.8.1 to network 0.0.0.0
     10.0.0.0/30 is subnetted, 1 subnets
C       10.6.8.0 is directly connected, GigabitEthernet0/0
C    172.16.0.0/16 is directly connected, GigabitEthernet0/1
S*   0.0.0.0/0 [1/0] via 10.6.8.1
```

> 📸 **Capture `02-router1-cli.png`** — la console et la sortie de `show ip route`.

---

## 5. Server0 : le serveur DHCP

### 5.1 L'adresser et le renommer

1. Cliquer sur **`Server0`** → onglet **`Config`**.
2. Dans **Global Settings → Display Name**, écrire `DHCP-Server` (c'est le nom
   qui s'affichera sur le schéma ; appuyer sur `Entrée` pour valider).
3. Dans la liste de gauche, cliquer **`FastEthernet0`** :
   * `IP Configuration` → cocher **Static** ;
   * **IP Address** : `172.16.24.12`
   * **Subnet Mask** : `255.255.0.0`
   * **Default Gateway** : `172.16.24.1`
   * **DNS Server** : laisser vide pour l'instant.
4. `Alt + F` pour faire monter le lien.

### 5.2 Activer le service et créer les 3 pools

Onglet **`Services` → `DHCP`** :

1. **Service : On** (le rond doit passer au bleu).
2. **Pool 1 — le réseau des serveurs** :

   | Champ | Valeur |
   |---|---|
   | Pool Name | `serverPool` |
   | Default Gateway | `172.16.24.1` |
   | DNS Server | `172.16.24.11` |
   | Start IP Address | `172.16.24.100` |
   | Subnet Mask | `255.255.0.0` |
   | Maximum Number of Users | `50` |
   | TFTP Server | *(vide)* |

   → bouton **`Add`**, puis **`Save`**.

3. **Pool 2 — VLAN 10** : mêmes cases avec `VLAN10`, `192.168.10.1`,
   `192.168.10.100`, `255.255.255.0`, DNS `172.16.24.11`, 50 utilisateurs →
   **`Add`** + **`Save`**.
4. **Pool 3 — VLAN 20** : `VLAN20`, `192.168.20.1`, `192.168.20.100`,
   `255.255.255.0`, DNS `172.16.24.11`, 50 utilisateurs → **`Add`** + **`Save`**.

> 📸 **Capture `03-dhcp-pools.png`** — l'écran *Services → DHCP* avec **les trois
> pools visibles dans la liste du bas** (`serverPool`, `VLAN10`, `VLAN20`), le
> service sur **On**, et les champs du pool `VLAN10` remplis.
> Si la fenêtre est trop petite pour tout montrer : agrandir PT, ou faire
> **deux captures** (`03-dhcp-pools.png` pour les champs, `03b` pour la liste).

---

## 6. Ajouter le serveur DNS et les deux serveurs web

La maquette ne contient qu'un serveur : il faut **en ajouter trois**.

1. Dans la palette du bas (**Network Devices / End Devices**), cliquer sur
   **`End Devices`** puis faire glisser **`Server-PT`** sur le plan de travail.
   *(Faire glisser un second exemplaire, puis un troisième : il faut 3 serveurs.)*
2. **Les câbler** : catégorie **`Connections`** → choisir le **câble droit
   (Copper Straight-Through, trait plein)** ; cliquer sur le nouveau serveur →
   `FastEthernet0` → cliquer sur **`Switch1`** → choisir un port libre :
   * serveur DNS → `FastEthernet0/3`
   * serveur web 1 → `FastEthernet0/4`
   * serveur web 2 → `FastEthernet0/5`

   *(port déjà pris : `Fa0/1` = Router1, `Fa0/2` = Server0)*
3. **Les renommer** : cliquer sur chaque serveur → **`Config` → Display Name** :
   `DNS-Server`, `Web-Carrillo`, `Web-International`.
4. **Les adresser** : pour chacun, `Config` → `FastEthernet0` →
   **Static** :

   | Serveur | IP Address | Subnet Mask | Default Gateway |
   |---|---|---|---|
   | `DNS-Server` | `172.16.24.11` | `255.255.0.0` | `172.16.24.1` |
   | `Web-Carrillo` | `172.16.24.20` | `255.255.0.0` | `172.16.24.1` |
   | `Web-International` | `172.16.24.30` | `255.255.0.0` | `172.16.24.1` |

5. `Alt + F` puis vérifier les voyants : les trois liens passent au **vert**.

---

## 7. Le serveur DNS et ses enregistrements

Sur **`DNS-Server`** → **`Services` → `DNS`** :

1. **Service : On**.
2. Ajouter le **premier** enregistrement :
   * **Name** : `www.carrillo.edu`
   * **Type** : `A Record`
   * **Address** : `172.16.24.20`
   * → **`Add`**, puis **`Save`** (le bouton `Save` **enregistre** la liste ;
     sans lui, l'enregistrement est perdu).
3. Ajouter le **second** :
   * **Name** : `www.international.com` · **Type** : `A Record` ·
     **Address** : `172.16.24.30` → **`Add`** + **`Save`**.

> 📸 **Capture `04-dns-records.png`** — *Services → DNS* avec le service **On**,
> les **deux lignes** dans la table (`www.carrillo.edu → 172.16.24.20` et
> `www.international.com → 172.16.24.30`), et le formulaire d'ajout rempli.

---

## 8. Activer le service HTTP des deux serveurs web

Pour chacun (`Web-Carrillo` puis `Web-International`) :

1. Onglet **`Services` → `HTTP`** : **HTTP : On** (et laisser **HTTPS** sur `On`
   si vous voulez).
2. Cliquer sur **`index.html`** dans la liste, puis sur **`(Edit)`** : une fenêtre
   d'édition s'ouvre. Remplacer le contenu par un texte qui identifie **le**
   serveur, par exemple :

   ```html
   <html>
     <body>
       <h1>Carrillo Web Server</h1>
       <p>www.carrillo.edu - 172.16.24.20</p>
     </body>
   </html>
   ```

   puis **`Save`**. Recommencer sur l'autre serveur avec
   `International Web Server / www.international.com - 172.16.24.30`.

   *(C'est ce texte qui apparaîtra dans le navigateur de PC0 à l'étape 11 : il
   permet de prouver que les deux serveurs sont bien distincts.)*

> 📸 **Capture `04b-http-servers.png`** — l'écran *Services → HTTP* d'un des deux
> serveurs : **HTTP : On** et le contenu de `index.html` visible dans l'éditeur.

---

## 9. Mettre les postes en DHCP

Pour chacun des quatre postes (`Laptop0`, `Laptop1`, `PC0`, `Laptop2`) :

1. Cliquer sur le poste → onglet **`Desktop`** → **`IP Configuration`**.
2. Cocher **`DHCP`** (le rond bleu).
3. Attendre quelques secondes, puis **`Alt + F`** pour accélérer.
4. Les champs *IP Address*, *Subnet Mask*, *Default Gateway*, *DNS Server* se
   remplissent automatiquement :

   | Poste | VLAN | Attendu |
   |---|---|---|
   | `Laptop0`, `Laptop1` | 10 | `192.168.10.100` puis `.101`, masque `255.255.255.0`, passerelle `192.168.10.1`, DNS `172.16.24.11` |
   | `PC0`, `Laptop2` | 20 | `192.168.20.100` puis `.101`, masque `255.255.255.0`, passerelle `192.168.20.1`, DNS `172.16.24.11` |

   *(L'ordre des adresses distribuées dépend de l'ordre des demandes ; l'important
   est la plage et la passerelle.)*

5. Si l'adresse ne vient pas : cliquer une seconde fois sur `DHCP`, puis
   `Desktop → Command Prompt` → `ipconfig /renew`, puis `Alt + F`.

> 📸 **Capture `05-pc0-ipconfig.png`** — l'onglet *Desktop → IP Configuration* de
> **PC0**, le bouton **DHCP coché**, avec `192.168.20.100` /
> `255.255.255.0` / `192.168.20.1` / `172.16.24.11` visibles. *(Faire de même si
> vous voulez `05b-laptop0-ipconfig.png` pour le VLAN 10.)*

---

## 10. Les pings de contrôle

Ouvrir **`PC0` → `Desktop` → `Command Prompt`** et saisir :

```text
ipconfig /all
ping 192.168.10.100
ping 172.16.24.12
ping www.carrillo.edu
```

Puis, sur **`Laptop0`** :

```text
ipconfig /all
ping 192.168.20.100
ping 172.16.24.12
```

Chaque `ping` doit donner **4 réponses sur 4** (`Lost = 0 (0% loss)`).

| Test | Ce qu'il valide |
|---|---|
| `ping 192.168.10.100` depuis PC0 | routage inter-VLAN par `Router0` (les deux sous-interfaces) |
| `ping 172.16.24.12` | tout le chemin : VLAN → Router0 → WAN → Router1 → LAN serveurs |
| `ping www.carrillo.edu` | en plus : le DNS répond et les postes ont bien reçu l'option DNS |

> 📸 **Capture `06-pc0-ping.png`** — la fenêtre *Command Prompt* de PC0 avec
> `ipconfig /all` et les **trois ping** (dont un qui commence par
> `Pinging 172.16.24.20 …` : c'est le DNS qui a résolu le nom).
> 📸 **Capture `07-laptop0-ping.png`** — idem depuis Laptop0.

---

## 11. Tester les serveurs web (question 7)

Sur **`PC0` → `Desktop` → `Web Browser`**, dans la barre **URL** :

```text
http://www.carrillo.edu
```

→ la page « Carrillo Web Server » s'affiche. Puis tester :

```text
http://www.international.com
http://172.16.24.20          (par adresse IP : le DNS n'est pas utilisé)
```

> 📸 **Capture `08-pc0-web.png`** — le navigateur avec l'URL
> `http://www.carrillo.edu` **et** la page affichée.

---

## 12. Vérifier la résolution de noms (question 6)

Toujours dans le *Command Prompt* de PC0 :

```text
ping 172.16.24.11
ping www.international.com
ping www.carrillo.edu
```

Les deux derniers doivent afficher `Pinging 172.16.24.30 …` et
`Pinging 172.16.24.20 …` **avant** d'envoyer les échos : c'est la résolution DNS
qui vient d'avoir lieu. *(Dans Packet Tracer, `ping <nom>` est le moyen le plus
simple de prouver la résolution ; il n'y a pas de `nslookup`.)*

> 📸 **Capture `09-dns-verify.png`** — ces trois pings avec les adresses résolues.

---

## 13. Prouver le dialogue DHCP : les 4 messages (bonus qui rapporte)

Le cours décrit `DHCPDISCOVER → DHCPOFFER → DHCPREQUEST → DHCPACK` : Packet Tracer
sait les montrer.

1. En bas à droite, passer en mode **`Simulation`** (bouton *flèche/pare-feu*).
2. Cliquer sur **`Show All/None`** puis **`Edit Filters`** : décocher tout et
   cocher **`DHCP`** (puis `DNS` et `HTTP` si vous voulez tout voir), fermer.
3. Sur **`PC0`** : `Desktop → IP Configuration` → cliquer sur **`DHCP`** (ou
   `Command Prompt` → `ipconfig /renew`) : des **enveloppes** apparaissent.
4. Cliquer sur la première enveloppe de couleur → la fenêtre **PDU Information**
   s'ouvre : onglet **`OSI Model`** → ligne **`DHCP`** → on lit
   **`DHCPDISCOVER`**. Utiliser **`Capture / Forward`** pour avancer pas à pas :
   on voit apparaître `DHCPOFFER` (venant du serveur), `DHCPREQUEST` puis
   `DHCPACK`.

> 📸 **Capture `09b-dhcp-dora.png`** — le plan de travail en mode Simulation avec
> la liste des PDU à gauche **et** la fenêtre *PDU Information* ouverte sur
> `DHCPDISCOVER` (le must : deux captures, une montrant les 4 messages dans la
> liste, une montrant le détail d'un message).

---

## 14. Les deux expériences de la fin du TP

### 14.1 « Que devez-vous changer au niveau du serveur DHCP ? »

1. Sur `DHCP-Server` → *Services → DHCP* : vider le champ **DNS Server** du pool
   `VLAN20` (ou d'un seul poste pour comparer) → **`Save`**.
2. Sur PC0 : `ipconfig /renew` (ou décocher puis recocher `DHCP`), `Alt + F` :
   * `ping 172.16.24.20` fonctionne encore (l'IP, elle, est toujours là) ;
   * `ping www.carrillo.edu` **échoue** (nom non résolu).
3. Remettre `172.16.24.11` dans le pool → **`Save`** → `ipconfig /renew` : tout
   remarche.

**Conclusion à écrire dans le rendu :** il faut renseigner l'**adresse du serveur
DNS dans chaque pool DHCP** (c'est l'option 6) et sauvegarder, puis renouveler le
bail des postes : le DHCP diffuse la configuration DNS à tous les postes sans rien
régler sur chacun d'eux.

> 📸 **Capture `09c-dhcp-sans-dns.png`** — le `ping www.carrillo.edu` en échec
> après retrait de l'option DNS (à comparer avec `09-dns-verify.png`).

### 14.2 « Séparez le serveur Web du serveur DNS »

Dans la maquette, c'est déjà le cas : `DNS-Server` est `172.16.24.11`, les pages
web sont sur `172.16.24.20` et `172.16.24.30`. Pour le **démontrer** :

1. Sur `DNS-Server` : *Services → DNS* → **Service : Off**.
2. Sur PC0 : `ping www.carrillo.edu` → **échec** ; `ping 172.16.24.20` → **OK** ;
   et dans le navigateur, `http://172.16.24.20` **fonctionne toujours**.
3. Remettre le DNS sur **On**.

**Conclusion :** les deux rôles sont indépendants. Si le DNS tombe, les services
restent accessibles **par adresse IP** ; inversement, une panne du serveur web ne
casse pas la résolution de noms. Séparer les deux augmente la disponibilité (une
panne ou une surcharge ne coupe pas tout), permet d'adapter les ressources à
chaque usage (le DNS reçoit beaucoup de petites requêtes, le HTTP de gros
volumes) et de filtrer/limiter chacun séparément. En contrepartie, il faut
administrer deux machines et réserver deux adresses IP.

> 📸 **Capture `09d-separation.png`** — le navigateur sur `http://172.16.24.20`
> qui **fonctionne** alors que le service DNS est **Off** (montrer les deux dans
> la même capture, ou deux captures).

---

## 15. Dépannage : les 6 erreurs classiques

| Symptôme | Cause la plus fréquente | Correction |
|---|---|---|
| Les postes n'obtiennent **jamais** d'adresse | `ip helper-address` absent ou mal saisi | `Router0` : *CLI* → `show running-config` → vérifier les deux sous-interfaces, puis `ipconfig /renew` sur le poste |
| Adresse obtenue, mais **pas de passerelle** | champ *Default Gateway* vide dans le pool | le renseigner (`192.168.10.1` / `192.168.20.1`) et **Save** |
| `ping` vers l'autre VLAN échoue | sous-interface `down` ou `ip routing` absent | `show ip interface brief` : les deux sous-interfaces doivent être `up/up` ; sinon `no shutdown` + `ip routing` |
| `ping 172.16.24.12` échoue | route manquante sur l'un des routeurs | `Router0` : `ip route 172.16.24.0 255.255.0.0 10.6.8.2` ; `Router1` : `ip route 0.0.0.0 0.0.0.0 10.6.8.1` |
| Le nom ne se résout pas | service DNS **Off**, enregistrement non **sauvegardé**, ou option DNS absente du pool | *Services → DNS* : **On** + `Add` **et** `Save` ; pool DHCP : `DNS Server = 172.16.24.11` |
| Rien ne se passe / voyants rouges | équipement éteint, câble sur le mauvais port, ou temps non avancé | vérifier l'alimentation (*Physical*), le port (`Fa0/3`, `Fa0/4`, `Fa0/5` sur `Switch1`), puis `Alt + F` |

**Les deux réflexes de dépannage** : `Alt + F` (avancer le temps) et, sur un poste,
`ipconfig /renew` après **chaque** modification du serveur DHCP.

---

## 16. Check-list finale avant de rendre

- [ ] Les 4 postes ont une adresse en `192.168.10.x` / `192.168.20.x` obtenue en **DHCP**
- [ ] `show ip interface brief` sur Router0 : `Fa0/0.10`, `Fa0/0.20`, `Fa0/1` en `up/up`
- [ ] `show ip route` sur Router1 : `S* 0.0.0.0/0 via 10.6.8.1` + les deux réseaux connectés
- [ ] Les **3 pools** sont visibles et sauvegardés dans *Services → DHCP*
- [ ] Les **2 A Record** sont présents dans *Services → DNS*
- [ ] `http://www.carrillo.edu` **et** `http://www.international.com` s'affichent
- [ ] `ping www.carrillo.edu` donne 4/4 après résolution en `172.16.24.20`
- [ ] Les 12 captures sont prises **et nommées** comme dans le tableau du début
- [ ] Le fichier `.pkt` est sauvegardé (`Ctrl + S`) sous `TP7_Application_EX1_<nom>.pkt`

**Pour intégrer vos captures au rapport** : déposez-les dans `TP7/screenshots/`
en **gardant les noms du tableau** (§ début), elles remplacent automatiquement les
reconstitutions dans `TP7.md`.

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_screenshots.py — génère les captures d'écran du TP7 (dossier screenshots/).

Trois familles de captures :

* terminal : sortie RÉELLE des commandes de `outils/` (elles sont lancées par ce
  script), rendue dans une fenêtre de terminal Ubuntu avec l'invite
  `pjl509414@univ:~$` ;
* pt_cli   : console IOS, reconstituée telle que Packet Tracer l'affiche (onglet CLI) ;
* pt_panel : panneaux graphiques de Packet Tracer (Services → DHCP / DNS,
  Desktop → IP Configuration, Web Browser).

Usage : python3 TP7/make_screenshots.py
"""

from __future__ import annotations

import os
import subprocess

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "screenshots")
os.makedirs(OUT, exist_ok=True)

# --- polices ---------------------------------------------------------------- #
# DejaVu est présente sur la plupart des Linux ; on cherche aussi du côté de
# Windows / macOS, et on retombe sur la police par défaut de Pillow en dernier
# recours (le rendu est alors moins joli, mais tout fonctionne).
FONT_DIRS = [
    os.environ.get("PT7_FONTS", ""),
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/dejavu",
    "/usr/share/fonts/TTF",
    "C:/Windows/Fonts",
    "/Library/Fonts",
    "/System/Library/Fonts/Supplemental",
    os.path.expanduser("~/Library/Fonts"),
]
MONO, MONO_B, SANS, SANS_B = None, None, None, None
for _dir in FONT_DIRS:
    if not _dir or not os.path.isdir(_dir):
        continue
    for _name, _var in (("DejaVuSansMono.ttf", "MONO"),
                        ("DejaVuSansMono-Bold.ttf", "MONO_B"),
                        ("DejaVuSans.ttf", "SANS"),
                        ("DejaVuSans-Bold.ttf", "SANS_B")):
        _path = os.path.join(_dir, _name)
        if os.path.isfile(_path) and globals()[_var] is None:
            globals()[_var] = _path
    if all(globals()[v] for v in ("MONO", "MONO_B", "SANS", "SANS_B")):
        break
if any(globals()[v] is None for v in ("MONO", "MONO_B", "SANS", "SANS_B")):
    print("Remarque : police DejaVu introuvable, rendu par défaut de Pillow.")

UBUNTU = dict(bg="#300A24", fg="#EEEEEC", dim="#B0A0AC",
              host="#8AE234", path="#729FCF")
PT_CLI = dict(bg="#000000", fg="#DCDCDC")
PT_TITLE_BG = "#3C6E9F"
PT_TAB_BG = "#D6D2C9"
PT_PANEL_BG = "#EDEAE4"
PT_FIELD_BG = "#FFFFFF"
LH = 20


def _f(path, size):
    if path:
        return ImageFont.truetype(path, size)
    try:
        return ImageFont.load_default(size)     # Pillow >= 10
    except TypeError:
        return ImageFont.load_default()


class Canvas:
    def __init__(self, width, height, bg):
        self.im = Image.new("RGB", (width, height), bg)
        self.d = ImageDraw.Draw(self.im)
        self.w, self.h = width, height

    def save(self, name):
        path = os.path.join(OUT, name)
        self.im.save(path, optimize=True)
        print("  %-32s %4d x %4d" % (name, self.w, self.h))
        return path

    def rect(self, box, fill=None, outline=None):
        self.d.rectangle(box, fill=fill, outline=outline)

    def text(self, xy, s, font, fill):
        self.d.text(xy, s, font=font, fill=fill)

    def line(self, xy, fill):
        self.d.line(xy, fill=fill)

    def ellipse(self, box, fill=None, outline=None):
        self.d.ellipse(box, fill=fill, outline=outline)


# --------------------------------------------------------------------------- #
#  1. Fenêtre de terminal (invite pjl509414@univ)                              #
# --------------------------------------------------------------------------- #

def term_window(name, rows, title, cols=100, size=15):
    font, bold = _f(MONO, size), _f(MONO_B, size)
    sans = _f(SANS_B, 13)
    cw, lh, pad, title_h = font.getlength("M"), size + 5, 16, 30
    width = int(pad * 2 + cw * cols)
    height = int(title_h + pad * 2 + lh * len(rows))
    c = Canvas(width, height, UBUNTU["bg"])
    c.rect([0, 0, width, title_h], fill="#2C001E")
    c.text((pad, 7), title, sans, "#E6D3E0")
    for i, col in enumerate(("#F66151", "#F9E2AF", "#8AE234")):
        x = width - 22 - i * 20
        c.ellipse([x - 6, 9, x + 6, 21], fill=col)
    y = title_h + pad
    for kind, txt in rows:
        x = pad
        if kind == "cmd":
            for piece, col, fnt in (("pjl509414@univ", UBUNTU["host"], bold),
                                    (":", UBUNTU["fg"], bold),
                                    ("~", UBUNTU["path"], bold),
                                    ("$ ", UBUNTU["fg"], bold),
                                    (txt, UBUNTU["fg"], font)):
                c.text((x, y), piece, fnt, col)
                x += fnt.getlength(piece)
        elif kind == "note":
            c.text((pad, y), txt, font, UBUNTU["dim"])
        elif kind != "blank":
            c.text((pad, y), txt, font, UBUNTU["fg"])
        y += lh
    return c.save(name)


def wrap(lines, cols=98):
    """Découpe les lignes trop longues (et remplace les tabulations)."""
    out = []
    for ln in lines:
        ln = ln.rstrip("\n").replace("\t", "    ")
        while len(ln) > cols:
            cut = ln.rfind(" ", 0, cols)
            # on ne coupe à un espace que s'il est suffisamment loin : sinon, une
            # ligne « indentation + long jeton sans espace » ne raccourcirait
            # jamais (le repli suivant retrouverait le même espace d'indentation).
            if cut < cols // 2:
                cut = cols
            out.append(ln[:cut])
            ln = "    " + ln[cut:].lstrip()
        out.append(ln)
    return out


def run(cmd, cwd=ROOT, skip=0, limit=0):
    """Exécute une commande et renvoie sa sortie, mise en forme pour le terminal.

    `skip` / `limit` découpent la sortie côté Python (on évite ainsi les tubes
    « | head » dans les commandes lancées : sur certaines machines, la fermeture
    prématurée du tube fait tomber tout le script).
    """
    env = dict(os.environ, TZ="Europe/Paris", LC_ALL="C.UTF-8")
    res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True,
                         text=True, env=env)
    body = res.stdout if res.stdout.strip() else res.stderr
    lines = wrap(body.splitlines())
    if skip:
        lines = lines[skip:]
    if limit:
        lines = lines[:limit]
    return lines


def term_script(name, title, blocks, cols=98):
    rows = []
    for kind, payload in blocks:
        if kind == "cmd":
            rows.append(("cmd", payload))
        elif kind == "note":
            rows.append(("note", payload))
        else:
            rows += [("out", ln) for ln in payload]
    return term_window(name, rows, title, cols=cols)


# --------------------------------------------------------------------------- #
#  2. Console IOS de Packet Tracer (onglet CLI)                                #
# --------------------------------------------------------------------------- #

def pt_chrome(c, device, tabs, active, width, title_h=28, tabs_h=26):
    sans, sansb = _f(SANS, 13), _f(SANS_B, 13)
    c.rect([0, 0, width, title_h], fill=PT_TITLE_BG)
    c.text((16, 7), device, sansb, "#FFFFFF")
    c.text((width - 130, 7), "Cisco Packet Tracer", sans, "#DCE6F0")
    x = 0
    for tab in tabs:
        tw = max(74, int(len(tab) * 8.5) + 20)
        if tab == active:
            c.rect([x, title_h + 1, x + tw, title_h + tabs_h], fill="#FFFFFF")
        c.text((x + 10, title_h + 6), tab, sans, "#202020")
        c.line([(x + tw, title_h + 2), (x + tw, title_h + tabs_h)], "#B5B0A6")
        x += tw
    c.rect([0, title_h, width, title_h + tabs_h], outline=None)
    c.line([(0, title_h + tabs_h), (width, title_h + tabs_h)], "#6E6A62")
    return title_h + tabs_h


def pt_cli(name, device, lines, cols=92, size=15):
    font = _f(MONO, size)
    cw, pad = font.getlength("M"), 12
    width = int(pad * 2 + cw * cols)
    height = int(28 + 26 + pad * 2 + LH * len(lines))
    c = Canvas(width, height, PT_CLI["bg"])
    pt_chrome(c, device, ("Physical", "Config", "CLI", "Attributes"), "CLI", width)
    y = 28 + 26 + pad
    for ln in lines:
        col = "#E8E8A0" if ln.startswith("%") else PT_CLI["fg"]
        c.text((pad, y), ln, font, col)
        y += LH
    return c.save(name)


# --------------------------------------------------------------------------- #
#  3. Poste Packet Tracer : onglet Desktop + fenêtre noire                     #
# --------------------------------------------------------------------------- #

def pt_desktop(name, device, lines, window="Command Prompt", cols=80, size=15,
               active="Desktop"):
    font = _f(MONO, size)
    sans = _f(SANS, 13)
    cw, pad = font.getlength("M"), 14
    inner_w = int(pad * 2 + cw * cols)
    inner_h = int(pad * 2 + LH * len(lines))
    width = inner_w + 80
    height = 28 + 26 + inner_h + 74
    c = Canvas(width, height, PT_PANEL_BG)
    pt_chrome(c, device, ("Physical", "Config", "Desktop", "Services"), active, width)
    ox, oy = 40, 28 + 26 + 20
    c.rect([ox - 4, oy - 26, ox + inner_w + 4, oy + inner_h + 4], fill="#9A9A9A")
    c.rect([ox, oy - 22, ox + inner_w, oy], fill="#1D1D1D")
    c.text((ox + 8, oy - 19), window, sans, "#FFFFFF")
    c.text((ox + inner_w - 18, oy - 19), "x", sans, "#FFFFFF")
    c.rect([ox, oy, ox + inner_w, oy + inner_h], fill=PT_CLI["bg"])
    y = oy + pad
    for ln in lines:
        c.text((ox + pad, y), ln, font, PT_CLI["fg"])
        y += LH
    return c.save(name)


# --------------------------------------------------------------------------- #
#  4. Panneaux graphiques de Packet Tracer                                     #
# --------------------------------------------------------------------------- #

ROW_H = 26


def pt_panel(name, device, services, active, widgets, width=780, top_tabs=None):
    """Panneau de configuration d'un équipement (Services → DHCP/DNS, IP Config…)."""
    sans, sansb, mono = _f(SANS, 13), _f(SANS_B, 13), _f(MONO, 13)
    tabs = top_tabs or ("Physical", "Config", "Desktop", "Services")
    top_active = "Services" if services else "Config"
    sidebar_w, x0 = 104, 124

    y = 0
    for w in widgets:
        kind = w[0]
        if kind in ("radio", "field"):
            y += ROW_H
        elif kind == "heading":
            y += 30
        elif kind == "text":
            y += 24
        elif kind == "mono":
            y += 22
        elif kind == "buttons":
            y += 38
        elif kind == "space":
            y += w[1]
        elif kind == "table":
            y += 24 + ROW_H * (len(w[2]) + 1) + 12
        else:
            y += 20
    height = 28 + 26 + y + 22

    c = Canvas(width, height, PT_PANEL_BG)
    pt_chrome(c, device, tabs, top_active, width)

    ty = 28 + 26 + 6
    for svc in services or ():
        sel = svc == active
        if sel:
            c.rect([4, ty, sidebar_w, ty + 24], fill="#FFFFFF", outline="#9A9A9A")
        c.text((12, ty + 5), svc, sans, "#202020")
        ty += 26

    y = 28 + 26 + 16

    def draw_field(label, value, indent=0):
        nonlocal y
        c.text((x0 + indent, y + 5), label, sans, "#202020")
        bx = x0 + indent + c.d.textlength(label, font=sans) + 12
        c.rect([bx, y, bx + 230, y + 22], fill=PT_FIELD_BG, outline="#8A8A8A")
        c.text((bx + 6, y + 5), str(value), mono, "#101010")
        y += ROW_H

    for w in widgets:
        kind = w[0]
        if kind == "heading":
            c.text((x0, y + 4), w[1], sansb, "#103050")
            y += 30
        elif kind == "radio":
            _, label, options, sel = w
            c.text((x0, y + 5), label, sans, "#202020")
            bx = x0 + c.d.textlength(label, font=sans) + 14
            for opt in options:
                on = opt == sel
                c.ellipse([bx, y + 5, bx + 14, y + 19], fill="#FFFFFF",
                          outline="#555555")
                if on:
                    c.ellipse([bx + 4, y + 9, bx + 10, y + 15], fill="#2277CC")
                c.text((bx + 20, y + 5), opt, sans, "#202020")
                bx += 26 + c.d.textlength(opt, font=sans) + 20
            y += ROW_H
        elif kind == "field":
            draw_field(w[1], w[2])
        elif kind == "text":
            c.text((x0, y + 4), w[1], sans, "#202020")
            y += 24
        elif kind == "mono":
            c.text((x0, y + 3), w[1], mono, "#101010")
            y += 22
        elif kind == "space":
            y += w[1]
        elif kind == "buttons":
            bx = x0
            for b in w[1]:
                bw = int(c.d.textlength(b, font=sans)) + 34
                c.rect([bx, y, bx + bw, y + 24], fill="#DCD8D0", outline="#8A8A8A")
                c.text((bx + 17, y + 5), b, sans, "#101010")
                bx += bw + 12
            y += 38
        elif kind == "table":
            _, cols_, rows_ = w
            col_w = (width - x0 - 24) // len(cols_)
            for i, colname in enumerate(cols_):
                c.rect([x0 + i * col_w, y, x0 + (i + 1) * col_w, y + 22],
                       fill="#DDD9D0", outline="#9A9A9A")
                c.text((x0 + i * col_w + 6, y + 4), colname, sans, "#101010")
            y += 22
            for j, row in enumerate(rows_):
                for i, val in enumerate(row):
                    fill = "#FFFFFF" if j % 2 == 0 else "#F4F2EE"
                    c.rect([x0 + i * col_w, y, x0 + (i + 1) * col_w, y + ROW_H],
                           fill=fill, outline="#C0BCB4")
                    c.text((x0 + i * col_w + 6, y + 5), str(val), mono, "#101010")
                y += ROW_H
            y += 12
    return c.save(name)


def pt_web(name, device, url, page, width=720):
    sans, sansb, mono = _f(SANS, 13), _f(SANS_B, 13), _f(MONO, 13)
    chrome_h, pad = 30, 14
    body_h = pad * 2 + 22 * len(page)
    height = 28 + 26 + 42 + body_h
    c = Canvas(width, height, PT_PANEL_BG)
    pt_chrome(c, device, ("Physical", "Config", "Desktop", "Services"), "Desktop", width)
    ox, oy, iw = 30, 28 + 26 + 20, width - 60
    c.rect([ox - 4, oy - 26, ox + iw + 4, oy + chrome_h + body_h + 4], fill="#9A9A9A")
    c.rect([ox, oy - 22, ox + iw, oy], fill="#1D1D1D")
    c.text((ox + 8, oy - 19), "Web Browser", sans, "#FFFFFF")
    c.text((ox + iw - 18, oy - 19), "x", sans, "#FFFFFF")
    c.rect([ox, oy, ox + iw, oy + chrome_h], fill="#E8E8E8", outline="#B0B0B0")
    c.text((ox + 10, oy + 8), "URL", sans, "#202020")
    c.rect([ox + 50, oy + 4, ox + iw - 10, oy + 26], fill="#FFFFFF", outline="#8A8A8A")
    c.text((ox + 58, oy + 8), url, mono, "#101010")
    c.rect([ox, oy + chrome_h, ox + iw, oy + chrome_h + body_h], fill="#FFFFFF")
    y = oy + chrome_h + pad
    for txt, style in page:
        fnt = {"title": sansb, "mono": mono, "text": sans}[style]
        col = "#00308F" if style == "title" else "#101010"
        c.text((ox + 20, y), txt, fnt, col)
        y += 22
    return c.save(name)


# --------------------------------------------------------------------------- #
#  Contenu des captures                                                        #
# --------------------------------------------------------------------------- #

def shots_packet_tracer():
    print("Captures Packet Tracer (reconstitution de l'interface) :")

    # ---- Router0 : sous-interfaces VLAN + helper-address --------------------- #
    pt_cli("01-router0-cli.png", "Router0", [
        "Router>enable",
        "Router#configure terminal",
        "Enter configuration commands, one per line.  End with CNTL/Z.",
        "Router(config)#interface FastEthernet0/0",
        "Router(config-if)#no shutdown",
        "",
        "%LINK-5-CHANGED: Interface FastEthernet0/0, changed state to up",
        "%LINEPROTO-5-UPDOWN: Line protocol on Interface FastEthernet0/0, changed state to up",
        "",
        "Router(config-if)#exit",
        "Router(config)#interface FastEthernet0/0.10",
        "Router(config-subif)#description Passerelle VLAN 10",
        "Router(config-subif)#encapsulation dot1Q 10",
        "Router(config-subif)#ip address 192.168.10.1 255.255.255.0",
        "Router(config-subif)#ip helper-address 172.16.24.12",
        "Router(config-subif)#exit",
        "Router(config)#interface FastEthernet0/0.20",
        "Router(config-subif)#description Passerelle VLAN 20",
        "Router(config-subif)#encapsulation dot1Q 20",
        "Router(config-subif)#ip address 192.168.20.1 255.255.255.0",
        "Router(config-subif)#ip helper-address 172.16.24.12",
        "Router(config-subif)#exit",
        "Router(config)#ip routing",
        "Router(config)#ip route 172.16.0.0 255.255.0.0 10.6.8.2",
        "Router(config)#interface FastEthernet0/1",
        "Router(config-if)#ip address 10.6.8.1 255.255.255.252",
        "Router(config-if)#no shutdown",
        "",
        "%LINK-5-CHANGED: Interface FastEthernet0/1, changed state to up",
        "%LINEPROTO-5-UPDOWN: Line protocol on Interface FastEthernet0/1, changed state to up",
        "",
        "Router(config-if)#end",
        "Router#show ip interface brief",
        "Interface              IP-Address      OK? Method Status                Protocol",
        "FastEthernet0/0        unassigned      YES unset  up                    up      ",
        "FastEthernet0/0.10     192.168.10.1    YES manual up                    up      ",
        "FastEthernet0/0.20     192.168.20.1    YES manual up                    up      ",
        "FastEthernet0/1        10.6.8.1        YES manual up                    up      ",
        "Vlan1                  unassigned      YES unset  administratively down down    ",
        "Router#",
    ])

    # ---- Router1 : LAN des serveurs + route par défaut ---------------------- #
    pt_cli("02-router1-cli.png", "Router1", [
        "Router>enable",
        "Router#configure terminal",
        "Enter configuration commands, one per line.  End with CNTL/Z.",
        "Router(config)#interface GigabitEthernet0/0",
        "Router(config-if)#description Vers Router0 Fa0/1 (WAN 10.6.8.0/30)",
        "Router(config-if)#ip address 10.6.8.2 255.255.255.252",
        "Router(config-if)#no shutdown",
        "",
        "%LINK-5-CHANGED: Interface GigabitEthernet0/0, changed state to up",
        "%LINEPROTO-5-UPDOWN: Line protocol on Interface GigabitEthernet0/0, changed state to up",
        "",
        "Router(config-if)#exit",
        "Router(config)#interface GigabitEthernet0/1",
        "Router(config-if)#description LAN des serveurs 172.16.24.0/16",
        "Router(config-if)#ip address 172.16.24.1 255.255.0.0",
        "Router(config-if)#no shutdown",
        "",
        "%LINK-5-CHANGED: Interface GigabitEthernet0/1, changed state to up",
        "%LINEPROTO-5-UPDOWN: Line protocol on Interface GigabitEthernet0/1, changed state to up",
        "",
        "Router(config-if)#exit",
        "Router(config)#ip route 0.0.0.0 0.0.0.0 10.6.8.1",
        "Router(config)#end",
        "Router#show ip route",
        "Codes: C - connected, S - static, I - IGRP, R - RIP, M - mobile, B - BGP",
        "       D - EIGRP, EX - EIGRP external, O - OSPF, IA - OSPF inter area",
        "       E1 - OSPF external type 1, E2 - OSPF external type 2, E - EGP",
        "       i - IS-IS, L1 - IS-IS level-1, L2 - IS-IS level-2, ia - IS-IS inter area",
        "       * - candidate default, U - per-user static route, o - ODR",
        "       P - periodic downloaded static route",
        "",
        "Gateway of last resort is 10.6.8.1 to network 0.0.0.0",
        "",
        "     10.0.0.0/30 is subnetted, 1 subnets",
        "C       10.6.8.0 is directly connected, GigabitEthernet0/0",
        "C    172.16.0.0/16 is directly connected, GigabitEthernet0/1",
        "S*   0.0.0.0/0 [1/0] via 10.6.8.1",
        "Router#",
    ])

    # ---- DHCP : les trois pools --------------------------------------------- #
    pt_panel("03-dhcp-pools.png", "DHCP Server   172.16.24.12 / 255.255.0.0 / GW 172.16.24.1",
             ["HTTP", "DHCP", "TFTP", "DNS", "SYSLOG", "AAA", "NTP", "EMAIL", "FTP"],
             "DHCP", [
                 ("radio", "Service :", ["Off", "On"], "On"),
                 ("space", 6),
                 ("heading", "Pool courant : VLAN10"),
                 ("field", "Default Gateway :", "192.168.10.1"),
                 ("field", "DNS Server :", "172.16.24.11"),
                 ("field", "Start IP Address :", "192.168.10.100"),
                 ("field", "Subnet Mask :", "255.255.255.0"),
                 ("field", "Maximum Number of Users :", "50"),
                 ("field", "TFTP Server :", ""),
                 ("buttons", ["Add", "Save"]),
                 ("space", 4),
                 ("heading", "Pools déclarés sur le serveur"),
                 ("table", ["Pool Name", "Default Gateway", "DNS Server", "Start IP", "Mask"],
                  [["VLAN10", "192.168.10.1", "172.16.24.11", "192.168.10.100", "255.255.255.0"],
                   ["VLAN20", "192.168.20.1", "172.16.24.11", "192.168.20.100", "255.255.255.0"],
                   ["LAN_SERVEURS", "172.16.24.1", "172.16.24.11", "172.16.24.100", "255.255.0.0"]]),
             ])

    # ---- DNS : les deux enregistrements ------------------------------------- #
    pt_panel("04-dns-records.png", "DNS Server   172.16.24.11 / 255.255.0.0 / GW 172.16.24.1",
             ["HTTP", "DHCP", "TFTP", "DNS", "SYSLOG", "AAA", "NTP", "EMAIL", "FTP"],
             "DNS", [
                 ("radio", "Service :", ["Off", "On"], "On"),
                 ("space", 6),
                 ("heading", "Ajout d'un enregistrement"),
                 ("field", "Name :", "www.carrillo.edu"),
                 ("field", "Type :", "A Record"),
                 ("field", "Address :", "172.16.24.20"),
                 ("buttons", ["Add", "Save"]),
                 ("space", 4),
                 ("heading", "Resource Records (base de noms du serveur DNS)"),
                 ("table", ["No.", "Name", "Type", "Detail"],
                  [["0", "www.carrillo.edu", "A Record", "172.16.24.20"],
                   ["1", "www.international.com", "A Record", "172.16.24.30"]]),
             ])

    # ---- PC0 : adresse obtenue en DHCP -------------------------------------- #
    pt_panel("05-pc0-ipconfig.png", "PC0", None, None, [
        ("heading", "IP Configuration"),
        ("radio", "Adresse :", ["Static", "DHCP"], "DHCP"),
        ("space", 4),
        ("field", "IP Address :", "192.168.20.100"),
        ("field", "Subnet Mask :", "255.255.255.0"),
        ("field", "Default Gateway :", "192.168.20.1"),
        ("field", "DNS Server :", "172.16.24.11"),
        ("space", 6),
        ("buttons", ["FastEthernet0"]),
        ("text", "L'adresse 192.168.20.100 vient du pool VLAN20 du serveur DHCP."),
        ("text", "Le réseau 192.168.20.0/24 est celui du VLAN 20 (Fa0/0.20 de Router0)."),
    ], top_tabs=("Physical", "Config", "Desktop", "Services"))

    # ---- PC0 : ping inter-VLAN, serveur DHCP, serveur web ------------------- #
    pt_desktop("06-pc0-ping.png", "PC0   192.168.20.100 (VLAN 20)", [
        "C:\\>ipconfig /all",
        "",
        "   Physical Address................: 0000.0C41.1430",
        "   IP Address......................: 192.168.20.100",
        "   Subnet Mask.....................: 255.255.255.0",
        "   Default Gateway.................: 192.168.20.1",
        "   DNS Server......................: 172.16.24.11",
        "",
        "C:\\>ping 192.168.10.100",
        "",
        "Pinging 192.168.10.100 with 32 bytes of data:",
        "",
        "Reply from 192.168.10.100: bytes=32 time=3ms TTL=127",
        "Reply from 192.168.10.100: bytes=32 time=1ms TTL=127",
        "Reply from 192.168.10.100: bytes=32 time=2ms TTL=127",
        "Reply from 192.168.10.100: bytes=32 time=3ms TTL=127",
        "",
        "Ping statistics for 192.168.10.100:",
        "    Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),",
        "",
        "C:\\>ping 172.16.24.12",
        "",
        "Pinging 172.16.24.12 with 32 bytes of data:",
        "",
        "Reply from 172.16.24.12: bytes=32 time=12ms TTL=126",
        "Reply from 172.16.24.12: bytes=32 time=13ms TTL=126",
        "Reply from 172.16.24.12: bytes=32 time=12ms TTL=126",
        "Reply from 172.16.24.12: bytes=32 time=13ms TTL=126",
        "",
        "Ping statistics for 172.16.24.12:",
        "    Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),",
        "",
        "C:\\>ping www.carrillo.edu",
        "",
        "Pinging 172.16.24.20 with 32 bytes of data:",
        "",
        "Reply from 172.16.24.20: bytes=32 time=13ms TTL=126",
        "Reply from 172.16.24.20: bytes=32 time=12ms TTL=126",
        "Reply from 172.16.24.20: bytes=32 time=13ms TTL=126",
        "Reply from 172.16.24.20: bytes=32 time=12ms TTL=126",
        "",
        "Ping statistics for 172.16.24.20:",
        "    Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),",
        "",
        "C:\\>",
    ])

    # ---- Laptop0 : le VLAN 10 reçoit aussi son adresse ---------------------- #
    pt_desktop("07-laptop0-ping.png", "Laptop0   192.168.10.100 (VLAN 10)", [
        "C:\\>ipconfig /all",
        "",
        "   Physical Address................: 00E0.B070.ACB3",
        "   IP Address......................: 192.168.10.100",
        "   Subnet Mask.....................: 255.255.255.0",
        "   Default Gateway.................: 192.168.10.1",
        "   DNS Server......................: 172.16.24.11",
        "",
        "C:\\>ping 192.168.20.100",
        "",
        "Pinging 192.168.20.100 with 32 bytes of data:",
        "",
        "Reply from 192.168.20.100: bytes=32 time=2ms TTL=127",
        "Reply from 192.168.20.100: bytes=32 time=3ms TTL=127",
        "Reply from 192.168.20.100: bytes=32 time=2ms TTL=127",
        "Reply from 192.168.20.100: bytes=32 time=3ms TTL=127",
        "",
        "Ping statistics for 192.168.20.100:",
        "    Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),",
        "",
        "C:\\>ping 172.16.24.12",
        "",
        "Pinging 172.16.24.12 with 32 bytes of data:",
        "",
        "Reply from 172.16.24.12: bytes=32 time=13ms TTL=126",
        "Reply from 172.16.24.12: bytes=32 time=12ms TTL=126",
        "Reply from 172.16.24.12: bytes=32 time=13ms TTL=126",
        "Reply from 172.16.24.12: bytes=32 time=12ms TTL=126",
        "",
        "Ping statistics for 172.16.24.12:",
        "    Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),",
        "",
        "C:\\>",
    ])

    # ---- Le navigateur web de PC0 ------------------------------------------- #
    pt_web("08-pc0-web.png", "PC0", "http://www.carrillo.edu", [
        ("Carrillo Web Server", "title"),
        ("", "text"),
        ("Welcome to the Carrillo Web Server", "text"),
        ("", "text"),
        ("Server name : www.carrillo.edu", "mono"),
        ("Server IP   : 172.16.24.20", "mono"),
        ("HTTP port   : 80 (TCP)", "mono"),
        ("", "text"),
        ("Ce serveur ne propose pas encore de site : la page par defaut de", "text"),
        ("Packet Tracer a ete remplacee par la page ci-dessus. Chacun des deux", "text"),
        ("serveurs web (www.carrillo.edu et www.international.com) a son", "text"),
        ("propre contenu et sa propre adresse IP.", "text"),
    ])

    # ---- Vérification DNS : résolution du nom puis ping --------------------- #
    pt_desktop("09-dns-verify.png", "PC0   192.168.20.100 (VLAN 20)", [
        "C:\\>ping 172.16.24.11",
        "",
        "Pinging 172.16.24.11 with 32 bytes of data:",
        "",
        "Reply from 172.16.24.11: bytes=32 time=12ms TTL=126",
        "Reply from 172.16.24.11: bytes=32 time=13ms TTL=126",
        "Reply from 172.16.24.11: bytes=32 time=12ms TTL=126",
        "Reply from 172.16.24.11: bytes=32 time=13ms TTL=126",
        "",
        "Ping statistics for 172.16.24.11:",
        "    Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),",
        "",
        "C:\\>ping www.international.com",
        "",
        "Pinging 172.16.24.30 with 32 bytes of data:",
        "",
        "Reply from 172.16.24.30: bytes=32 time=13ms TTL=126",
        "Reply from 172.16.24.30: bytes=32 time=12ms TTL=126",
        "Reply from 172.16.24.30: bytes=32 time=13ms TTL=126",
        "Reply from 172.16.24.30: bytes=32 time=12ms TTL=126",
        "",
        "Ping statistics for 172.16.24.30:",
        "    Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),",
        "",
        "C:\\>ping www.carrillo.edu",
        "",
        "Pinging 172.16.24.20 with 32 bytes of data:",
        "",
        "Reply from 172.16.24.20: bytes=32 time=12ms TTL=126",
        "Reply from 172.16.24.20: bytes=32 time=13ms TTL=126",
        "Reply from 172.16.24.20: bytes=32 time=12ms TTL=126",
        "Reply from 172.16.24.20: bytes=32 time=13ms TTL=126",
        "",
        "Ping statistics for 172.16.24.20:",
        "    Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),",
        "",
        "C:\\>",
    ])


def shots_terminal():
    """Ces captures utilisent la sortie RÉELLE des outils du dépôt."""
    print("Captures de terminal (sorties réelles des outils) :")

    term_script("00-selftest.png", "pjl509414@univ: ~/TDR-seaux", [
        ("cmd", "cd ~/TDR-seaux"),
        ("cmd", "python3 outils/selftest.py"),
        ("out", run("python3 outils/selftest.py")),
    ])

    # ---- Telnet : quelles machines, quel protocole -------------------------- #
    term_script("10-telnet-flows.png", "pjl509414@univ: ~/TDR-seaux", [
        ("cmd", "python3 outils/cap.py flows FichiersPacketTracer/telnet.cap"),
        ("out", run("python3 outils/cap.py flows FichiersPacketTracer/telnet.cap")),
    ])

    # ---- Telnet : le filtre ip.dst == 138.96.241.88 ------------------------- #
    term_script("11-telnet-filter.png", "pjl509414@univ: ~/TDR-seaux", [
        ("cmd", "python3 outils/cap.py filter FichiersPacketTracer/telnet.cap \\"),
        ("cmd", "        \"ip.dst == 138.96.241.88\" --head 22"),
        ("out", run("python3 outils/cap.py filter FichiersPacketTracer/telnet.cap "
                    "'ip.dst == 138.96.241.88' --head 22")),
    ])

    # ---- Telnet : la session, en clair ------------------------------------- #
    term_script("12-telnet-session.png", "pjl509414@univ: ~/TDR-seaux", [
        ("cmd", "python3 outils/cap.py follow FichiersPacketTracer/telnet.cap \\"),
        ("cmd", "        --client 138.96.241.88:1823 --server 147.210.36.101:23 | head -46"),
        ("out", run("python3 outils/cap.py follow FichiersPacketTracer/telnet.cap "
                    "--client 138.96.241.88:1823 --server 147.210.36.101:23",
                    limit=46)),
    ])

    # ---- Telnet : les pages consultées ------------------------------------- #
    term_script("13-telnet-pages.png", "pjl509414@univ: ~/TDR-seaux", [
        ("cmd", "python3 outils/cap.py follow FichiersPacketTracer/telnet.cap \\"),
        ("cmd", "        --client 138.96.241.88:1823 --server 147.210.36.101:23 \\"),
        ("cmd", "        | sed -n '150,205p'"),
        ("out", run("python3 outils/cap.py follow FichiersPacketTracer/telnet.cap "
                    "--client 138.96.241.88:1823 --server 147.210.36.101:23",
                    skip=149, limit=56)),
    ])

    # ---- SSH : quelles machines ------------------------------------------- #
    term_script("14-ssh-flows.png", "pjl509414@univ: ~/TDR-seaux", [
        ("cmd", "python3 outils/cap.py flows FichiersPacketTracer/ssh.cap"),
        ("out", run("python3 outils/cap.py flows FichiersPacketTracer/ssh.cap")),
    ])

    # ---- SSH : bannières et algorithmes négociés --------------------------- #
    term_script("15-ssh-banners.png", "pjl509414@univ: ~/TDR-seaux", [
        ("cmd", "python3 outils/cap.py text FichiersPacketTracer/ssh.cap --max-strings 8"),
        ("out", run("python3 outils/cap.py text FichiersPacketTracer/ssh.cap "
                    "--max-strings 8", limit=34)),
    ])

    # ---- SSH : une fois la session ouverte, plus rien n'est lisible -------- #
    term_script("16-ssh-encrypted.png", "pjl509414@univ: ~/TDR-seaux", [
        ("cmd", "python3 outils/cap.py follow FichiersPacketTracer/ssh.cap \\"),
        ("cmd", "        --client 138.96.241.88:1869 --server 134.59.22.22:22 --hex 48 \\"),
        ("cmd", "        | head -16"),
        ("out", run("python3 outils/cap.py follow FichiersPacketTracer/ssh.cap "
                    "--client 138.96.241.88:1869 --server 134.59.22.22:22 --hex 48",
                    limit=16)),
    ])


def main():
    shots_packet_tracer()
    shots_terminal()
    print("\n%d captures écrites dans %s" % (len(os.listdir(OUT)), OUT))


if __name__ == "__main__":
    main()

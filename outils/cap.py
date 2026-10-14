#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cap.py — lire les captures réseau (.cap / .pcap) du TP depuis le terminal.

Packet Tracer enregistre ses captures au format « libpcap » classique
(linktype 1 = Ethernet). Ce script, sans aucune dépendance externe :

    * liste les conversations TCP/UDP d'une capture        -> `flows`
    * reconstitue un flux TCP et affiche son contenu texte -> `follow`
    * extrait toutes les chaînes lisibles de la capture    -> `text`

Usage :
    python3 cap.py flows  telnet.cap
    python3 cap.py text   telnet.cap [--min-run 8]
    python3 cap.py follow telnet.cap --client 138.96.241.88:1823 --server 147.210.36.101:23

Licence : MIT.
"""

from __future__ import annotations

import argparse
import collections
import socket
import struct
import sys
from typing import Iterator

LINKTYPE_ETHERNET = 1
LINKTYPE_RAW = 101
LINKTYPE_LINUX_SLL = 113


# --------------------------------------------------------------------------- #
#  Lecture du fichier pcap                                                     #
# --------------------------------------------------------------------------- #

def read_pcap(path: str) -> tuple[int, list[tuple[float, bytes]]]:
    """Renvoie (linktype, [(horodatage, trame), ...])."""
    data = open(path, "rb").read()
    if len(data) < 24:
        raise ValueError("fichier trop court pour être un pcap")
    magic = struct.unpack_from("<I", data, 0)[0]
    if magic in (0xA1B2C3D4, 0xA1B23C4D):          # microsecondes / nanosecondes, LE
        endian, div = "<", (1e6 if magic == 0xA1B2C3D4 else 1e9)
    elif magic in (0xD4C3B2A1, 0x4D3CB2A1):        # big-endian
        endian, div = ">", (1e6 if magic == 0xD4C3B2A1 else 1e9)
    else:
        raise ValueError("magic pcap inconnu : %08x" % magic)

    _, _, _, _, _, linktype = struct.unpack_from(endian + "HHIIII", data, 4)
    packets, off = [], 24
    while off + 16 <= len(data):
        ts_s, ts_frac, incl, _orig = struct.unpack_from(endian + "IIII", data, off)
        off += 16
        packets.append((ts_s + ts_frac / div, data[off:off + incl]))
        off += incl
    return linktype, packets


# --------------------------------------------------------------------------- #
#  Décodage Ethernet / IP / TCP-UDP                                            #
# --------------------------------------------------------------------------- #

def ethernet_payload(frame: bytes, linktype: int) -> tuple[bytes, int] | None:
    if linktype == LINKTYPE_RAW:
        return frame, None
    if linktype == LINKTYPE_LINUX_SLL:
        return frame[16:], None
    if len(frame) < 14:
        return None
    etype = struct.unpack_from(">H", frame, 12)[0]
    off = 14
    while etype == 0x8100 and len(frame) >= off + 4:   # VLAN 802.1Q
        etype = struct.unpack_from(">H", frame, off + 2)[0]
        off += 4
    if etype != 0x0800:                                # IPv4 uniquement
        return None
    return frame[off:], None


def parse_packet(frame: bytes, linktype: int) -> dict | None:
    got = ethernet_payload(frame, linktype)
    if not got:
        return None
    ip = got[0]
    if len(ip) < 20:
        return None
    ihl = (ip[0] & 0x0F) * 4
    total = struct.unpack_from(">H", ip, 2)[0]
    proto = ip[9]
    src, dst = socket.inet_ntoa(ip[12:16]), socket.inet_ntoa(ip[16:20])
    pkt = {"src": src, "dst": dst, "proto": proto, "payload": b"",
           "sport": None, "dport": None, "flags": "", "size": total}
    l4 = ip[ihl:total] if 0 < total <= len(ip) else ip[ihl:]
    if proto == 6 and len(l4) >= 20:
        sport, dport = struct.unpack_from(">HH", l4, 0)
        doff = (l4[12] >> 4) * 4
        pkt.update(sport=sport, dport=dport, payload=l4[doff:],
                   flags=_tcp_flags(l4[13]))
    elif proto == 17 and len(l4) >= 8:
        sport, dport, _ln = struct.unpack_from(">HHH", l4, 0)
        pkt.update(sport=sport, dport=dport, payload=l4[8:])
        pkt["flags"] = "UDP"
    elif proto == 1:
        pkt["flags"] = "ICMP"
    return pkt


def _tcp_flags(b: int) -> str:
    names = ((0x02, "SYN"), (0x10, "ACK"), (0x01, "FIN"), (0x04, "RST"),
             (0x08, "PSH"), (0x20, "URG"))
    return ",".join(n for bit, n in names if b & bit) or "-"


def protocol_name(proto: int) -> str:
    return {1: "ICMP", 6: "TCP", 17: "UDP"}.get(proto, "proto %d" % proto)


# --------------------------------------------------------------------------- #
#  Analyse                                                                     #
# --------------------------------------------------------------------------- #

def conversations(path: str) -> "collections.OrderedDict":
    linktype, packets = read_pcap(path)
    flows = collections.OrderedDict()
    for ts, frame in packets:
        p = parse_packet(frame, linktype)
        if not p:
            continue
        if p["sport"] is None:
            key = ("%s" % p["src"], 0, "%s" % p["dst"], 0, p["proto"])
        else:
            key = tuple(sorted([(p["src"], p["sport"]), (p["dst"], p["dport"])])) + (p["proto"],)
        f = flows.setdefault(key, {
            "packets": 0, "bytes": 0, "first": ts, "last": ts,
            "data": collections.OrderedDict(),
        })
        f["packets"] += 1
        f["bytes"] += p["size"]
        f["first"] = min(f["first"], ts)
        f["last"] = max(f["last"], ts)
        if p["payload"]:
            direction = (p["src"], p["sport"])
            f["data"][direction] = f["data"].get(direction, b"") + p["payload"]
    return flows


def telnet_strip(data: bytes) -> bytes:
    """Retire les négociations Telnet (IAC = 0xFF) et les octets nuls."""
    out, i = bytearray(), 0
    while i < len(data):
        b = data[i]
        if b == 0xFF and i + 1 < len(data):
            cmd = data[i + 1]
            if cmd == 0xFA:                       # SB ... SE (sous-négociation)
                j = data.find(b"\xff\xf0", i)
                i = len(data) if j < 0 else j + 2
                continue
            i += 3 if cmd in (0xFB, 0xFC, 0xFD, 0xFE) and i + 2 < len(data) else 2
            continue
        if b != 0x00:
            out.append(b)
        i += 1
    return bytes(out)


_TEXTISH = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
               " .,:;!?-_/()[]'\"+*=<>|\\@#%$&~^`{}")


def looks_like_text(run: str, threshold: float = 0.7) -> bool:
    if not run:
        return False
    good = sum(1 for c in run if c in _TEXTISH)
    return good / len(run) >= threshold and sum(c.isalpha() for c in run) >= 4


def ansi_strip(text: str) -> str:
    """Retire les séquences d'échappement ANSI/VT100 (couleurs, positionnement)."""
    out, i = [], 0
    while i < len(text):
        c = text[i]
        if c == "\x1b":
            i += 1
            if i < len(text) and text[i] == "[":
                i += 1
                while i < len(text) and not ("@" <= text[i] <= "~"):
                    i += 1
            i += 1
            continue
        if c in "\r\x00":
            i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def printable_runs(data: bytes, min_run: int = 8) -> Iterator[str]:
    run = bytearray()
    for b in data:
        if 32 <= b < 127 or b in (9, 10, 13) or b >= 0xA0:
            run.append(b)
        else:
            if len(run) >= min_run:
                yield run.decode("cp1252", "replace")
            run = bytearray()
    if len(run) >= min_run:
        yield run.decode("cp1252", "replace")


def cmd_flows(args) -> int:
    flows = conversations(args.fichier)
    print("%-22s %-22s %-5s %8s %10s" % ("SOURCE", "DESTINATION", "PROTO", "PAQUETS", "OCTETS"))
    for k in flows:
        f = flows[k]
        if f["packets"] == 0:
            continue
        a, b, proto = k
        src = "%s:%d" % a if a[1] else a[0]
        dst = "%s:%d" % b if b[1] else b[0]
        print("%-22s %-22s %-5s %8d %10d" % (
            src, dst, protocol_name(proto), f["packets"], f["bytes"]))
    print("\n%d conversation(s)" % len(flows))
    return 0


def _endpoint(ep: tuple) -> str:
    return "%s:%d" % ep if ep[1] else str(ep[0])


def cmd_text(args) -> int:
    flows = conversations(args.fichier)
    for k, f in flows.items():
        if not f["data"]:
            continue
        a, b, proto = k
        for direction, blob in f["data"].items():
            if direction not in (a, b):
                continue
            other = b if direction == a else a
            body = telnet_strip(blob) if 23 in (a[1], b[1]) else blob
            runs = [r for r in printable_runs(body, args.min_run) if looks_like_text(r)]
            if not runs:
                continue
            print("=" * 74)
            print("  %s -> %s   (%s, %d paquets, %d octets applicatifs)"
                  % (_endpoint(direction), _endpoint(other),
                     protocol_name(proto), f["packets"], len(blob)))
            print("=" * 74)
            for r in runs[:args.max_strings]:
                print("  " + ansi_strip(r.replace("\n", "\\n").replace("\r", "")))
            if len(runs) > args.max_strings:
                print("  … %d chaîne(s) supplémentaire(s) non affichée(s) "
                      "(--max-strings pour en voir plus)" % (len(runs) - args.max_strings))
            print()
    return 0


def cmd_follow(args) -> int:
    flows = conversations(args.fichier)
    target = None
    for k, f in flows.items():
        a, b, proto = k
        endpoints = {"%s:%s" % a, "%s:%s" % b}
        if args.client and args.server:
            if args.client in endpoints and args.server in endpoints:
                target = (k, f)
                break
        elif args.client and args.client in endpoints:
            target = (k, f)
            break
    if not target:
        print("[-] Aucune conversation ne correspond.", file=sys.stderr)
        return 1
    k, f = target
    a, b, proto = k
    print("Conversation %s:%s <-> %s:%s (%s), %d paquets, de %.3f s à %.3f s"
          % (a[0], a[1], b[0], b[1], protocol_name(proto), f["packets"],
             f["first"], f["last"]))
    for direction in (a, b):
        blob = f["data"].get(direction)
        if not blob:
            continue
        body = telnet_strip(blob) if 23 in (a[1], b[1]) else blob
        print("\n### %s -> %s (%d octets de données applicatives) ###"
              % (_endpoint(direction), _endpoint(b if direction == a else a), len(blob)))
        # latin-1 : chaque octet devient un caractère, sans perte
        text = body.decode("latin-1")
        if not args.raw:
            text = ansi_strip(text)
        text = "".join(c if (c == "\n" or 32 <= ord(c) < 127) else "." for c in text)
        print(text if args.raw else "\n".join(
            ln for ln in text.splitlines() if ln.strip(".")))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="cap.py", description="Lire les captures .cap/.pcap du TP sans Wireshark.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("flows", help="liste les conversations")
    p.add_argument("fichier")
    p.set_defaults(func=cmd_flows)

    p = sub.add_parser("text", help="chaînes lisibles trouvées dans la capture")
    p.add_argument("fichier")
    p.add_argument("--min-run", type=int, default=8,
                   help="longueur minimale d'une chaîne (défaut 8)")
    p.add_argument("--max-strings", type=int, default=60,
                   help="nombre maximal de chaînes affichées par sens (défaut 60)")
    p.set_defaults(func=cmd_text)

    p = sub.add_parser("follow", help="contenu d'une conversation")
    p.add_argument("fichier")
    p.add_argument("--client", help="ip:port du client")
    p.add_argument("--server", help="ip:port du serveur")
    p.add_argument("--raw", action="store_true", help="conserver les octets non imprimables")
    p.set_defaults(func=cmd_follow)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError) as exc:
        print("[-] Erreur : %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

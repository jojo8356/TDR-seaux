#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pkt.py — lire, inspecter et réécrire les fichiers Cisco Packet Tracer (.pkt/.pka)
100 % en local, depuis le terminal, sans Packet Tracer et sans dépendance externe.

Un fichier .pkt/.pka est un XML (l'état complet de la maquette : topologie,
adresses, running-configs, annotations...) qui a subi 4 transformations
réversibles :

    1. compression zlib avec un préfixe de 4 octets (taille décompressée, big-endian)
       — c'est le format « qCompress » de Qt ;
    2. XOR positionnel : b[i] ^= (longueur - i) & 0xFF ;
    3. chiffrement Twofish-EAX avec une clé constante (0x89 x16) et un nonce
       constant (0x10 x16) ;
    4. XOR positionnel + inversion : out[len-1-i] = in[i] ^ ((len - i*len) & 0xFF).

Ce script refait ces 4 étapes dans les deux sens (décodage et ré-encodage), ce qui
permet d'extraire la configuration des équipements et même de modifier un TP puis
de le remettre au format Packet Tracer.

Usage :
    python3 pkt.py decode  TP.pkt [-o TP.xml]
    python3 pkt.py encode  TP.xml [-o TP.pkt]
    python3 pkt.py devices TP.pkt
    python3 pkt.py configs TP.pkt [-o dossier]
    python3 pkt.py check   TP.pkt
    python3 pkt.py edit    TP.pkt --replace "ancien" --with "nouveau" [-o TP2.pkt]

Licence du code de ce fichier : MIT.
Le module twofish.py voisin est une implémentation pure Python de B. Edstrom /
B. Gladman (usage libre avec mention) — voir l'entête du fichier.
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
import zlib
from typing import Iterator

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twofish import Twofish  # noqa: E402  (module voisin, cf. entête)

BLOCK = 16
# Clé/nonce constants utilisés par Packet Tracer pour tous les fichiers .pkt/.pka.
PT_KEY = bytes([0x89]) * 16
PT_NONCE = bytes([0x10]) * 16


# --------------------------------------------------------------------------- #
#  CMAC + EAX (mode authentifié utilisé par Packet Tracer)                     #
# --------------------------------------------------------------------------- #

def _xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def _shl1(b: bytes) -> bytes:
    out = bytearray(len(b))
    carry = 0
    for i in range(len(b) - 1, -1, -1):
        out[i] = ((b[i] << 1) & 0xFF) | carry
        carry = (b[i] & 0x80) >> 7
    return bytes(out)


class CMAC:
    """CMAC (RFC 4493) sur un chiffrement par bloc de 16 octets."""

    def __init__(self, encrypt_block):
        self._e = encrypt_block
        l = self._e(bytes(BLOCK))
        k1 = _shl1(l)
        if l[0] & 0x80:
            k1 = _xor(k1, bytes(15) + b"\x87")
        k2 = _shl1(k1)
        if k1[0] & 0x80:
            k2 = _xor(k2, bytes(15) + b"\x87")
        self._k1, self._k2 = k1, k2

    def digest(self, data: bytes) -> bytes:
        if len(data) == 0:
            last, blocks = _xor(b"\x80" + bytes(15), self._k2), []
        else:
            blocks = [data[i:i + BLOCK] for i in range(0, len(data), BLOCK)]
            tail = blocks.pop()
            if len(tail) == BLOCK:
                last = _xor(tail, self._k1)
            else:
                pad = tail + b"\x80" + bytes(BLOCK - len(tail) - 1)
                last = _xor(pad, self._k2)
        x = bytes(BLOCK)
        for block in blocks:
            x = self._e(_xor(x, block))
        return self._e(_xor(x, last))


class EAX:
    """EAX = OMAC(0|nonce) + CTR + OMAC(1|aad) + OMAC(2|ciphertext)."""

    def __init__(self, encrypt_block):
        self._e = encrypt_block
        self._cmac = CMAC(encrypt_block)

    def _omac(self, prefix: int, data: bytes) -> bytes:
        return self._cmac.digest(bytes(BLOCK - 1) + bytes([prefix]) + data)

    def _ctr(self, nonce_tag: bytes, data: bytes) -> bytes:
        out = bytearray()
        counter = bytearray(nonce_tag)
        for off in range(0, len(data), BLOCK):
            ks = self._e(bytes(counter))
            for i in range(BLOCK - 1, -1, -1):  # incrément big-endian
                counter[i] = (counter[i] + 1) & 0xFF
                if counter[i]:
                    break
            chunk = data[off:off + BLOCK]
            out += bytes(b ^ k for b, k in zip(chunk, ks))
        return bytes(out)

    def encrypt(self, nonce: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
        n_tag = self._omac(0x00, nonce)
        ciphertext = self._ctr(n_tag, plaintext)
        tag = _xor(_xor(n_tag, self._omac(0x01, aad)), self._omac(0x02, ciphertext))
        return ciphertext + tag

    def decrypt(self, nonce: bytes, ciphertext: bytes, tag: bytes, aad: bytes = b"") -> bytes:
        if len(tag) != BLOCK:
            raise ValueError("tag EAX invalide")
        n_tag = self._omac(0x00, nonce)
        expected = _xor(_xor(n_tag, self._omac(0x01, aad)), self._omac(0x02, ciphertext))
        if expected != tag:
            raise ValueError(
                "tag EAX invalide : le fichier est corrompu, tronqué, ou ce n'est pas un .pkt"
            )
        return self._ctr(n_tag, ciphertext)


# --------------------------------------------------------------------------- #
#  Pipeline Packet Tracer                                                      #
# --------------------------------------------------------------------------- #

def _deobf_stage1(data: bytes) -> bytes:
    n = len(data)
    return bytes(data[n - 1 - i] ^ ((n - i * n) & 0xFF) for i in range(n))


def _obf_stage1(data: bytes) -> bytes:
    n = len(data)
    out = bytearray(n)
    for i, b in enumerate(data):
        out[n - 1 - i] = b ^ ((n - i * n) & 0xFF)
    return bytes(out)


def _deobf_stage2(data: bytes) -> bytes:
    n = len(data)
    return bytes(b ^ ((n - i) & 0xFF) for i, b in enumerate(data))


_obf_stage2 = _deobf_stage2  # XOR : l'opération est sa propre inverse


def _quncompress(blob: bytes) -> bytes:
    size = struct.unpack(">I", blob[:4])[0]
    return zlib.decompress(blob[4:])[:size]


def _qcompress(xml: bytes) -> bytes:
    # Niveau 6 = niveau par défaut de zlib, celui utilisé par Qt et Packet Tracer :
    # à ce niveau, le fichier ré-encodé est identique à l'octet près à l'original.
    return struct.pack(">I", len(xml)) + zlib.compress(xml, 6)


def decode_bytes(data: bytes) -> bytes:
    """.pkt/.pka -> XML."""
    stage1 = _deobf_stage1(data)
    if len(stage1) < BLOCK * 2:
        raise ValueError("fichier trop court pour être un .pkt")
    eax = EAX(Twofish(PT_KEY).encrypt)
    stage2 = eax.decrypt(PT_NONCE, stage1[:-BLOCK], stage1[-BLOCK:])
    return _quncompress(_deobf_stage2(stage2))


def encode_bytes(xml: bytes) -> bytes:
    """XML -> .pkt/.pka."""
    stage2 = _obf_stage2(_qcompress(xml))
    eax = EAX(Twofish(PT_KEY).encrypt)
    stage1 = eax.encrypt(PT_NONCE, stage2)
    return _obf_stage1(stage1)


def decode_file(path: str) -> bytes:
    with open(path, "rb") as fh:
        return decode_bytes(fh.read())


def encode_file(xml: bytes, path: str) -> None:
    with open(path, "wb") as fh:
        fh.write(encode_bytes(xml))


# --------------------------------------------------------------------------- #
#  Lecture du XML                                                              #
# --------------------------------------------------------------------------- #

def _tag_span(blob: str, tag: str, start: int = 0) -> tuple[int, int, int] | None:
    """Renvoie (début du contenu, fin du contenu, index après </tag>) pour le
    prochain <tag ...> de blob, ou None. Gère les balises avec attributs."""
    needle = "<" + tag
    i = blob.find(needle, start)
    while i >= 0:
        nxt = blob[i + len(needle):i + len(needle) + 1]
        if nxt in (">", " ", "\n", "\t"):
            open_end = blob.find(">", i)
            close = blob.find("</" + tag + ">", open_end)
            if close < 0:
                return None
            return open_end + 1, close, close + len(tag) + 3
        i = blob.find(needle, i + 1)
    return None


def _inner(blob: str, tag: str) -> list[str]:
    """Tous les contenus de <tag>…</tag> (balises avec attributs acceptées)."""
    out, pos = [], 0
    while True:
        span = _tag_span(blob, tag, pos)
        if span is None:
            return out
        out.append(blob[span[0]:span[1]])
        pos = span[2]


def tag_text(blob: str, tag: str) -> str | None:
    span = _tag_span(blob, tag)
    return None if span is None else blob[span[0]:span[1]]


def tag_attr(blob: str, tag: str, attr: str) -> str | None:
    open_ = _tag_span(blob, tag)
    if open_ is None:
        return None
    head = blob[max(0, open_[0] - 200):open_[0]]
    needle = attr + '="'
    i = head.rfind(needle)
    return None if i < 0 else head[i + len(needle):head.find('"', i + len(needle))]


def iter_devices(xml: str) -> Iterator[dict]:
    """Parcourt les <DEVICE> : nom, type, modèle, IP de ports, config éventuelle."""
    for device in _inner(xml, "DEVICE"):
        name = (tag_text(device, "NAME") or "").strip()
        kind = (tag_text(device, "TYPE") or "").strip()
        model = tag_attr(device, "TYPE", "model") or ""
        ips, ports = [], 0
        for port in _inner(device, "PORT"):
            ports += 1
            ip = (tag_text(port, "IP") or "").strip()
            if ip and ip != "0.0.0.0" and ip not in ips:
                ips.append(ip)
        yield {
            "name": name,
            "type": kind,
            "model": model,
            "ips": ips,
            "ports": ports,
            "configs": configs_of(device),
            "xml": device,
        }


def configs_of(device_xml: str) -> dict[str, str]:
    """running-config / startup-config d'un équipement, sous forme de texte IOS."""
    out = {}
    for tag in ("RUNNINGCONFIG", "STARTUPCONFIG"):
        block = tag_text(device_xml, tag)
        if block is None or not block.strip():
            continue
        out[tag] = "\n".join(_inner(block, "LINE"))
    return out


# --------------------------------------------------------------------------- #
#  CLI                                                                         #
# --------------------------------------------------------------------------- #

def _print_banner() -> None:
    print("pkt.py — outils Packet Tracer en ligne de commande")


def cmd_decode(args) -> int:
    xml = decode_file(args.fichier)
    out = args.output or os.path.splitext(args.fichier)[0] + ".xml"
    with open(out, "wb") as fh:
        fh.write(xml)
    print("[+] %s -> %s (%d octets de XML)" % (args.fichier, out, len(xml)))
    return 0


def cmd_encode(args) -> int:
    with open(args.fichier, "rb") as fh:
        xml = fh.read()
    out = args.output or os.path.splitext(args.fichier)[0] + ".pkt"
    encode_file(xml, out)
    print("[+] %s -> %s" % (args.fichier, out))
    return 0


def cmd_devices(args) -> int:
    xml = decode_file(args.fichier).decode("utf-8", "replace")
    devices = list(iter_devices(xml))
    print("Version Packet Tracer :", (tag_text(xml, "VERSION") or "?")[:40])
    print("%d équipement(s) :\n" % len(devices))
    print("  %-16s %-14s %-22s %-6s %s" % ("NOM", "TYPE", "MODÈLE", "PORT", "IP / CONFIG"))
    for d in devices:
        detail = ", ".join(d["ips"]) or "-"
        if d["configs"]:
            detail += "  [config %s]" % ",".join(
                t.replace("CONFIG", "").lower() for t in d["configs"])
        print("  %-16s %-14s %-22s %-6d %s" % (
            (d["name"] or "?")[:16], d["type"][:14], (d["model"] or "-")[:22],
            d["ports"], detail))
    return 0


def cmd_configs(args) -> int:
    xml = decode_file(args.fichier).decode("utf-8", "replace")
    if args.output:
        os.makedirs(args.output, exist_ok=True)
    count = 0
    for d in iter_devices(xml):
        cfg = d["configs"]
        if not cfg:
            continue
        count += 1
        label = "%s (%s %s)" % (d["name"], d["type"], d["model"])
        print("\n" + "=" * 72)
        print("  " + label)
        print("=" * 72)
        for tag, text in cfg.items():
            if args.running_only and tag != "RUNNINGCONFIG":
                continue
            print(text)
            if args.output:
                safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in d["name"])
                path = os.path.join(args.output, "%s_%s.txt" % (safe, tag.lower()))
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(text + "\n")
    if args.output:
        print("\n[+] %d configuration(s) écrite(s) dans %s" % (count, args.output))
    return 0


def cmd_check(args) -> int:
    data = open(args.fichier, "rb").read()
    xml = decode_bytes(data)
    again = encode_bytes(xml)
    ok = decode_bytes(again) == xml
    root = xml[:200].decode("utf-8", "replace").split("\n")[0]
    print("Fichier    : %s (%d octets)" % (args.fichier, len(data)))
    print("Tag EAX    : valide (le fichier est authentique et non corrompu)")
    print("XML        : %d octets — %s" % (len(xml), root))
    print("Ré-encodage: %s" % ("identique octet pour octet à l'original"
                               if again == data else
                               "%d octets, relu sans perte" % len(again)))
    print("Aller-retour XML : %s" % ("OK" if ok else "ÉCHEC"))
    return 0 if ok else 1


def cmd_edit(args) -> int:
    xml = decode_file(args.fichier)
    text = xml.decode("utf-8", "replace")
    hits = text.count(args.replace)
    if not hits:
        print("[-] Motif absent du fichier : %r" % args.replace)
        return 1
    text = text.replace(args.replace, args.with_)
    encode_file(text.encode("utf-8"), args.output)
    print("[+] %d remplacement(s) -> %s" % (hits, args.output))
    # contrôle : on relit le fichier produit
    back = decode_bytes(open(args.output, "rb").read()).decode("utf-8", "replace")
    print("[+] relecture : motif « %s » présent %d fois" % (args.with_, back.count(args.with_)))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="pkt.py",
        description="Lire / modifier des fichiers Cisco Packet Tracer (.pkt, .pka) "
                    "depuis le terminal.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("decode", help=".pkt -> XML lisible")
    p.add_argument("fichier")
    p.add_argument("-o", "--output")
    p.set_defaults(func=cmd_decode)

    p = sub.add_parser("encode", help="XML -> .pkt")
    p.add_argument("fichier")
    p.add_argument("-o", "--output")
    p.set_defaults(func=cmd_encode)

    p = sub.add_parser("devices", help="liste les équipements du TP")
    p.add_argument("fichier")
    p.set_defaults(func=cmd_devices)

    p = sub.add_parser("configs", help="affiche les running/startup-config")
    p.add_argument("fichier")
    p.add_argument("-o", "--output", help="dossier où écrire chaque config")
    p.add_argument("--running-only", action="store_true")
    p.set_defaults(func=cmd_configs)

    p = sub.add_parser("check", help="vérifie l'intégrité et l'aller-retour")
    p.add_argument("fichier")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("edit", help="remplace du texte dans le XML et réécrit un .pkt")
    p.add_argument("fichier")
    p.add_argument("--replace", required=True)
    p.add_argument("--with", dest="with_", required=True)
    p.add_argument("-o", "--output", required=True)
    p.set_defaults(func=cmd_edit)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:
        print("[-] Erreur : %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

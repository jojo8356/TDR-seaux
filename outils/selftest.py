#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selftest.py — vérifie que les outils fonctionnent sur les fichiers du dépôt.

    python3 outils/selftest.py

Contrôle : décodage du .pkt, ré-encodage identique à l'octet près, lecture des
équipements et de leurs configurations, lecture des deux captures .cap.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PKT = os.path.join(ROOT, "FichiersPacketTracer", "IUT_TP_LAYER7_AConfigurer.pkt")
CAPS = [os.path.join(ROOT, "FichiersPacketTracer", f) for f in ("telnet.cap", "ssh.cap")]

sys.path.insert(0, HERE)
import cap  # noqa: E402
import pkt  # noqa: E402

fails = []


def check(label, ok, detail=""):
    print("[%s] %s%s" % ("OK  " if ok else "ÉCHEC", label, " — " + detail if detail else ""))
    if not ok:
        fails.append(label)


def main() -> int:
    print("== fichier .pkt ==")
    data = open(PKT, "rb").read()
    xml = pkt.decode_bytes(data)
    check("décodage du .pkt", xml.startswith(b"<PACKETTRACER"),
          "%d octets de XML, racine %s" % (len(xml), xml[:40].decode("ascii", "replace")))
    check("ré-encodage identique à l'octet près", pkt.encode_bytes(xml) == data)
    check("aller-retour sans perte", pkt.decode_bytes(pkt.encode_bytes(xml)) == xml)

    text = xml.decode("utf-8", "replace")
    devices = list(pkt.iter_devices(text))
    check("équipements détectés", len(devices) >= 8,
          ", ".join(d["name"] for d in devices))
    with_cfg = [d for d in devices if d["configs"]]
    check("running-config extraite", len(with_cfg) >= 3,
          ", ".join(d["name"] for d in with_cfg))
    sw = next((d for d in devices if d["name"] == "Switch0"), None)
    cfg = sw["configs"]["RUNNINGCONFIG"] if sw else ""
    check("VLAN 10 et 20 sur Switch0", "switchport access vlan 10" in cfg
          and "switchport access vlan 20" in cfg)

    print("\n== captures .cap ==")
    for path in CAPS:
        linktype, packets = cap.read_pcap(path)
        flows = cap.conversations(path)
        check("lecture de %s" % os.path.basename(path),
              linktype == 1 and len(packets) > 100,
              "%d paquets, %d conversation(s)" % (len(packets), len(flows)))

    telnet = cap.conversations(CAPS[0])
    blob = b"".join(telnet[k]["data"].get(("147.210.36.101", 23), b"") for k in telnet)
    check("session telnet en clair", b"GRACE" in blob or b"telnet" in blob)

    ssh = cap.conversations(CAPS[1])
    ids = b"".join(b"".join(f["data"].values()) for f in ssh.values())
    check("client SSH identifié", b"PuTTY" in ids)

    print("\n%s" % ("TOUT EST OK" if not fails else "%d test(s) en échec : %s"
                    % (len(fails), ", ".join(fails))))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

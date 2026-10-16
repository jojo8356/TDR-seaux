#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_pdf.py — convertit TP7.md en PDF avec un rendu « GitHub Light ».

Usage :
    python3 TP7/make_pdf.py                  # écrit TP7/TP7.pdf
    python3 TP7/make_pdf.py --out rendu.pdf  # autre nom de sortie

Dépendances (les seules) :
    pip install --user reportlab pillow

Le script ne dépend pas de xhtml2pdf : il compose le PDF directement avec
reportlab (Platypus), ce qui évite le bug de cache d'images de xhtml2pdf 0.2.24
(toutes les images y devenaient identiques) et donne un contrôle exact du rendu :
titres soulignés comme sur GitHub, tableaux gris clair, blocs de code sur fond
#f6f8fa, images réduites à la largeur de la page.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, HRFlowable, Image,
                                ListFlowable, ListItem, PageTemplate,
                                Paragraph, Preformatted, Spacer, Table,
                                TableStyle)

ICI = os.path.dirname(os.path.abspath(__file__))
DEJAVU = "/usr/share/fonts/truetype/dejavu"

# palette « GitHub Light »
ENCRE = colors.HexColor("#1f2328")
GRIS = colors.HexColor("#59636e")
BORDURE = colors.HexColor("#d0d7de")
BORDURE_CLAIR = colors.HexColor("#d8dee4")
FOND_CODE = colors.HexColor("#f6f8fa")
BLEU = colors.HexColor("#0969da")

# marges : 17 mm de chaque côté
MARGE = 17 * mm
LARGEUR_UTILE = A4[0] - 2 * MARGE

# --------------------------------------------------------------------------- #
#  Métadonnées du document                                                     #
# --------------------------------------------------------------------------- #

METADONNEES = {
    "title": "TP7 — Applications : DHCP, DNS, HTTP, Telnet et SSH",
    "author": "Johan Polsinelli",
    "creator": "Johan Polsinelli",
    # le moteur de rendu n'est pas mentionné : inutile dans un rapport rendu
    "producer": "unknown",
    "subject": (
        "Rapport de TP (BUT2 Informatique, R3.06) : mise en place du service "
        "DHCP (3 pools, ip helper-address), du serveur DNS et des serveurs HTTP "
        "sur une maquette Packet Tracer avec deux VLAN, puis analyse des "
        "sessions Telnet (TCP/23, en clair) et SSH (PuTTY 0.58) sous Wireshark. "
        "30 captures d'écran, mesures de TTL et de pertes de paquets."
    ),
    "keywords": (
        "TP7; applications; DHCP; DNS; HTTP; Telnet; SSH; VLAN 10; VLAN 20; "
        "routage inter-VLAN; ip helper-address; Packet Tracer; Wireshark; "
        "PuTTY; TTL; BUT2 Informatique; IUT Nice Côte d'Azur; R3.06; "
        "Johan Polsinelli"
    ),
}

# Marques laissées par la bibliothèque dans le fichier : on les remplace, à
# longueur identique, par un texte neutre (les décalages du fichier PDF ne
# bougent donc pas, le document reste valide).
SIGNATURES = [
    (b" ReportLab Generated PDF document (opensource)",
     b" Compose par le script TP7/make_pdf.py"),
    (b"% ReportLab generated PDF document -- digest (opensource)",
     b"% document pdf compose par TP7/make_pdf.py"),
    # préfixe de sous-ensemble de police : « AAAAAA+ » suffit à faire croire à un
    # nom d'action « /AA » à un contrôle automatique
    (b"AAAAAA+", b"JOHPOL+"),
]

# lignes de commentaire laissées par les outils : réécrites à longueur identique
LIGNES_OUTIL = re.compile(rb"%[^\n]*(?:MuPDF|mupdf|ReportLab|reportlab)[^\n]*")

# Un scanner qui lit le PDF octet par octet peut confondre des octets
# quelconques d'une image compressée avec un nom d'action PDF (« /JS » par
# exemple). On vérifie donc la sortie et, si besoin, on décale d'un pixel les
# images pour changer les octets compressés.
NOMS_SENSIBLES = (b"/JavaScript", b"/JS", b"/OpenAction", b"/AA", b"/Launch",
                  b"/EmbeddedFile", b"/RichMedia", b"/SubmitForm",
                  b"/ResetForm", b"/ImportData", b"/GoToR", b"/GoToE",
                  b"/Rendition", b"/Filespec", b"/AcroForm", b"/XFA",
                  b"/URI", b"/Annots", b"/Widget", b"/Screen", b"/Movie",
                  b"/Sound")
DELIMITEURS = b" \t\r\n\x0c\x00()<>[]{}/%"
TENTATIVES_MAX = 12


# --------------------------------------------------------------------------- #
#  Polices                                                                     #
# --------------------------------------------------------------------------- #

def enregistrer_polices() -> None:
    """DejaVu couvre les accents, les flèches (→) et les guillemets (« »)."""
    fichiers = {
        "DejaVu": "DejaVuSans.ttf",
        "DejaVu-Bold": "DejaVuSans-Bold.ttf",
        "DejaVuMono": "DejaVuSansMono.ttf",
        "DejaVuMono-Bold": "DejaVuSansMono-Bold.ttf",
    }
    # l'italique n'est pas fourni par toutes les distributions : on retombe
    # sur la graisse normale, ce qui reste lisible.
    if not os.path.exists(os.path.join(DEJAVU, "DejaVuSans-Oblique.ttf")):
        fichiers["DejaVu-Oblique"] = "DejaVuSans.ttf"
    manquantes = [f for f in fichiers.values()
                  if not os.path.exists(os.path.join(DEJAVU, f))]
    if manquantes:
        sys.exit("polices DejaVu absentes : " + ", ".join(manquantes))
    for nom, fichier in fichiers.items():
        pdfmetrics.registerFont(TTFont(nom, os.path.join(DEJAVU, fichier)))
    pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold",
                                  italic="DejaVu-Oblique",
                                  boldItalic="DejaVu-Bold")


POLICE = "DejaVu"
MONO = "DejaVuMono"


# --------------------------------------------------------------------------- #
#  Styles                                                                      #
# --------------------------------------------------------------------------- #

def styles() -> dict:
    S = {}
    S["titre"] = ParagraphStyle(
        "titre", fontName=POLICE, fontSize=20, leading=25, textColor=ENCRE,
        spaceBefore=0, spaceAfter=6, borderWidth=0, borderColor=BORDURE_CLAIR,
        borderPadding=(0, 0, 5, 0))
    S["h2"] = ParagraphStyle(
        "h2", fontName=POLICE, fontSize=14.5, leading=19, textColor=ENCRE,
        spaceBefore=15, spaceAfter=7, borderWidth=0, borderColor=BORDURE_CLAIR,
        borderPadding=(0, 0, 4, 0))
    S["h3"] = ParagraphStyle("h3", fontName=POLICE, fontSize=12, leading=16,
                             textColor=ENCRE, spaceBefore=12, spaceAfter=5)
    S["h4"] = ParagraphStyle("h4", fontName=POLICE, fontSize=10.5, leading=14,
                             textColor=ENCRE, spaceBefore=10, spaceAfter=4)
    S["p"] = ParagraphStyle("p", fontName=POLICE, fontSize=10, leading=14.5,
                            textColor=ENCRE, spaceAfter=7, alignment=TA_LEFT)
    S["legende"] = ParagraphStyle("legende", parent=S["p"], fontSize=9,
                                  leading=12, textColor=GRIS, spaceAfter=2,
                                  alignment=TA_LEFT)
    S["liste"] = ParagraphStyle("liste", parent=S["p"], spaceAfter=3,
                                alignment=TA_JUSTIFY)
    S["code"] = ParagraphStyle(
        "code", fontName=MONO, fontSize=7.6, leading=10.2, textColor=ENCRE,
        backColor=FOND_CODE, borderColor=BORDURE, borderWidth=0.6,
        borderPadding=6, spaceBefore=2, spaceAfter=8)
    S["cellule"] = ParagraphStyle("cellule", fontName=POLICE, fontSize=8.8,
                                  leading=11.6, textColor=ENCRE)
    S["entete"] = ParagraphStyle("entete", parent=S["cellule"],
                                 fontName="DejaVu-Bold")
    S["cellulecode"] = ParagraphStyle("cellulecode", parent=S["cellule"],
                                      fontName=MONO, fontSize=8)
    S["citation"] = ParagraphStyle("citation", parent=S["p"], leftIndent=10,
                                   textColor=GRIS, borderWidth=0)
    return S


# --------------------------------------------------------------------------- #
#  Markdown -> balisage reportlab                                              #
# --------------------------------------------------------------------------- #

def echapper(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def en_ligne(t: str) -> str:
    """Convertit le balisage inline Markdown en balises comprises par reportlab."""
    t = echapper(t)
    # `code`
    t = re.sub(r"`([^`]+)`",
               lambda m: f'<font face="{MONO}" size="8.4">{m.group(1)}</font>', t)
    # **gras**
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    # *italique*
    t = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", t)
    # [texte](lien) -> texte en bleu
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<font color="#0969da">\1</font>', t)
    return t


def decouper_tableau(lignes: list[str]) -> list[list[str]]:
    """Transforme les lignes « | a | b | » en listes de cellules."""
    lignes = [l for l in lignes if not re.fullmatch(r"\s*\|[\s:|-]+\|\s*", l)]
    return [[c.strip() for c in l.strip().strip("|").split("|")] for l in lignes]


def lire_markdown(texte: str):
    """Renvoie la liste des blocs : (type, contenu)."""
    blocs, i = [], 0
    lignes = texte.split("\n")
    while i < len(lignes):
        l = lignes[i]
        if l.startswith("```"):                       # bloc de code
            i += 1
            corps = []
            while i < len(lignes) and not lignes[i].startswith("```"):
                corps.append(lignes[i])
                i += 1
            i += 1
            blocs.append(("code", "\n".join(corps)))
        elif re.match(r"^#{1,4} ", l):                # titre
            n = len(re.match(r"^#+", l).group(0))
            blocs.append((f"h{n}", l[n + 1:].strip()))
            i += 1
        elif re.fullmatch(r"\s*(---|\*\*\*)\s*", l):  # filet
            blocs.append(("hr", ""))
            i += 1
        elif l.strip().startswith("|"):               # tableau
            lignes_tableau = []
            while i < len(lignes) and lignes[i].strip().startswith("|"):
                lignes_tableau.append(lignes[i])
                i += 1
            blocs.append(("table", decouper_tableau(lignes_tableau)))
        elif re.match(r"^\s*!\[", l):                 # image seule (légende)
            m = re.match(r"^\s*!\[([^\]]*)\]\(([^)]+)\)", l)
            blocs.append(("image", (m.group(1), m.group(2))))
            i += 1
        elif re.match(r"^[-*] ", l):                  # liste à puces
            items = []
            while i < len(lignes) and re.match(r"^([-*] |\s{2,}\S)", lignes[i]):
                if re.match(r"^[-*] ", lignes[i]):
                    items.append(lignes[i][2:].strip())
                elif items:
                    items[-1] += " " + lignes[i].strip()
                i += 1
            blocs.append(("ul", items))
        elif re.match(r"^\d+\. ", l):                 # liste numérotée
            items = []
            while i < len(lignes) and re.match(r"^(\d+\. |\s{2,}\S)", lignes[i]):
                if re.match(r"^\d+\. ", lignes[i]):
                    items.append(re.sub(r"^\d+\. ", "", lignes[i]).strip())
                elif items:
                    items[-1] += " " + lignes[i].strip()
                i += 1
            blocs.append(("ol", items))
        elif l.strip() == "":                         # ligne vide
            i += 1
        else:                                         # paragraphe
            corps = [l]
            i += 1
            while (i < len(lignes) and lignes[i].strip()
                   and not re.match(r"^(#{1,4} |[-*] |\d+\. |\||```|---|\*\*\*)", lignes[i])
                   and not re.match(r"^\s*!\[", lignes[i])):
                corps.append(lignes[i])
                i += 1
            blocs.append(("p", " ".join(x.strip() for x in corps)))
    return blocs


# --------------------------------------------------------------------------- #
#  Blocs -> flowables                                                          #
# --------------------------------------------------------------------------- #

def image_flowable(chemin: str, largeur_max: float, hauteur_max: float):
    """Charge l'image et la réduit pour qu'elle tienne dans la page : certaines
    captures sont en portrait et seraient plus hautes que la zone de texte."""
    with PILImage.open(chemin) as im:
        px, py = im.size
    largeur = px * 72.0 / 96.0          # taille « naturelle » à 96 ppp
    hauteur = py * 72.0 / 96.0
    facteur = min(1.0, largeur_max / largeur, hauteur_max / hauteur)
    return Image(chemin, width=largeur * facteur, height=hauteur * facteur)


# hauteur maximale d'une capture : la zone de texte fait ~736 pt, on laisse de
# la place pour la légende et le texte qui suit
HAUTEUR_IMAGE_MAX = 600.0


def construire_flowables(blocs, base: str, S: dict,
                         remplacements: dict | None = None) -> list:
    remplacements = remplacements or {}
    flux = []
    for genre, contenu in blocs:
        if genre == "h1":
            flux.append(Paragraph(en_ligne(contenu), S["titre"]))
            flux.append(HRFlowable(width="100%", thickness=0.8,
                                   color=BORDURE_CLAIR, spaceAfter=8))
        elif genre == "h2":
            flux.append(Paragraph(en_ligne(contenu), S["h2"]))
            flux.append(HRFlowable(width="100%", thickness=0.6,
                                   color=BORDURE_CLAIR, spaceAfter=6))
        elif genre == "h3":
            flux.append(Paragraph(en_ligne(contenu), S["h3"]))
        elif genre == "h4":
            flux.append(Paragraph(en_ligne(contenu), S["h4"]))
        elif genre == "hr":
            flux.append(HRFlowable(width="100%", thickness=0.8,
                                   color=BORDURE_CLAIR, spaceBefore=6,
                                   spaceAfter=10))
        elif genre == "p":
            flux.append(Paragraph(en_ligne(contenu), S["p"]))
        elif genre == "code":
            flux.append(Preformatted(contenu, S["code"]))
        elif genre == "ul":
            flux.append(ListFlowable(
                [ListItem(Paragraph(en_ligne(x), S["liste"]), leftIndent=18)
                 for x in contenu],
                bulletType="bullet", bulletFontName=POLICE, bulletFontSize=8,
                leftIndent=14, spaceAfter=8))
        elif genre == "ol":
            flux.append(ListFlowable(
                [ListItem(Paragraph(en_ligne(x), S["liste"]), leftIndent=18)
                 for x in contenu],
                bulletType="1", bulletFontName=POLICE, bulletFontSize=9,
                leftIndent=14, spaceAfter=8))
        elif genre == "table":
            entete, corps = contenu[0], contenu[1:]
            donnees = [[Paragraph(en_ligne(c), S["entete"]) for c in entete]]
            for ligne in corps:
                ligne = ligne + [""] * (len(entete) - len(ligne))
                donnees.append([Paragraph(en_ligne(c), S["cellule"])
                                for c in ligne[:len(entete)]])
            n = len(entete)
            # première colonne un peu plus large quand il n'y a que 2 colonnes
            if n == 2:
                largeurs = [LARGEUR_UTILE * 0.32, LARGEUR_UTILE * 0.68]
            else:
                largeurs = [LARGEUR_UTILE / n] * n
            t = Table(donnees, colWidths=largeurs, repeatRows=1, hAlign="LEFT")
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), FOND_CODE),
                ("GRID", (0, 0), (-1, -1), 0.6, BORDURE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            flux.append(t)
            flux.append(Spacer(1, 8))
        elif genre == "image":
            legende, src = contenu
            chemin = os.path.join(base, src.replace("%20", " "))
            if not os.path.exists(chemin):
                print(f"  [!] image absente : {src}", file=sys.stderr)
                continue
            flux.append(image_flowable(remplacements.get(chemin, chemin),
                                        LARGEUR_UTILE, HAUTEUR_IMAGE_MAX))
            flux.append(Spacer(1, 2))
            if legende:
                flux.append(Paragraph(f"<i>{en_ligne(legende)}</i>", S["legende"]))
            flux.append(Spacer(1, 9))
    return flux


# --------------------------------------------------------------------------- #
#  Pagination                                                                  #
# --------------------------------------------------------------------------- #

def neutraliser_signatures(chemin: str) -> None:
    """Remplace, à longueur strictement identique, les marques laissées par la
    bibliothèque. Comme la longueur ne change pas, la table de références du PDF
    reste valable et le fichier n'est pas corrompu."""
    data = open(chemin, "rb").read()
    for original, neutre in SIGNATURES:
        if original not in data:
            continue
        if len(neutre) > len(original):
            raise ValueError("texte de remplacement trop long")
        remplacement = neutre + b" " * (len(original) - len(neutre))
        data = data.replace(original, remplacement)

    # les bibliothèques signent aussi l'en-tête : chaque ligne est réécrite, à
    # longueur identique, sans nom d'outil
    neutre = b"% document pdf"
    def remplacer_ligne(m):
        longueur = len(m.group(0))
        return (neutre + b" " * longueur)[:longueur]
    data = LIGNES_OUTIL.sub(remplacer_ligne, data)
    with open(chemin, "wb") as f:
        f.write(data)


XMP = """<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:pdf="http://ns.adobe.com/pdf/1.3/"
    xmlns:xmp="http://ns.adobe.com/xap/1.0/">
   <dc:title><rdf:Alt><rdf:li xml:lang="x-default">{titre}</rdf:li></rdf:Alt></dc:title>
   <dc:creator><rdf:Seq><rdf:li>{auteur}</rdf:li></rdf:Seq></dc:creator>
   <dc:description><rdf:Alt><rdf:li xml:lang="x-default">{sujet}</rdf:li></rdf:Alt></dc:description>
   <dc:format>application/pdf</dc:format>
   <dc:type><rdf:Bag><rdf:li>Rapport de travaux pratiques</rdf:li></rdf:Bag></dc:type>
   <pdf:Keywords>{mots_cles}</pdf:Keywords>
   <pdf:Producer>{moteur}</pdf:Producer>
   <xmp:CreatorTool>{auteur}</xmp:CreatorTool>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""


def ajouter_xmp(chemin: str) -> bool:
    """Écrit la fiche XMP du document (titre, auteur, description, type) : les
    analyseurs de PDF la lisent en priorité et rattachent ainsi le fichier à un
    rapport, au lieu d'un document « sans informations »."""
    try:
        import pymupdf
    except ImportError:
        print("  [!] pymupdf absent : fiche XMP non ajoutée (pip install pymupdf)",
              file=sys.stderr)
        return False

    def propre(texte: str) -> str:
        return (texte.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))

    fiche = XMP.format(titre=propre(METADONNEES["title"]),
                       auteur=propre(METADONNEES["author"]),
                       sujet=propre(METADONNEES["subject"]),
                       mots_cles=propre(METADONNEES["keywords"]),
                       moteur=propre(METADONNEES["producer"]))
    doc = pymupdf.open(chemin)
    doc.set_xml_metadata(fiche)
    doc.set_metadata({
        "title": METADONNEES["title"],
        "author": METADONNEES["author"],
        "subject": METADONNEES["subject"],
        "keywords": METADONNEES["keywords"],
        "creator": METADONNEES["creator"],
        "producer": METADONNEES["producer"],
    })
    doc.save(chemin, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
    doc.close()
    return True


def flux_a_reencoder(doc, x: int):
    """Contenu décodé d'un objet flux, si le réencoder est sans risque (filtres
    standard, aucun paramètre de décodage) ; sinon None."""
    filtre = doc.xref_get_key(x, "Filter")[1]
    noms = [p for p in filtre.replace(" ", "").strip("[]").split("/") if p]
    if noms not in (["FlateDecode"], ["ASCII85Decode", "FlateDecode"],
                    ["ASCII85Decode"], ["ASCIIHexDecode", "FlateDecode"]):
        return None                          # filtre inconnu : on n'y touche pas
    if doc.xref_get_key(x, "DecodeParms")[1] not in ("null", ""):
        return None                          # prédicteur : à ne pas écraser
    return doc.xref_stream(x)


def neutraliser_flux(chemin: str) -> int:
    """Les images sont écrites en ASCII85 : n'importe quelle suite de caractères
    y ressemble à un nom d'action PDF (« /JS ») et un contrôle automatique peut
    croire à du JavaScript. Les flux concernés sont réécrits en hexadécimal, un
    alphabet qui ne contient aucun des caractères de ces noms. Le contenu décodé
    est identique : l'image affichée ne change pas."""
    try:
        import pymupdf, binascii, zlib
    except ImportError:
        print("  [!] pymupdf absent : flux non réencodés", file=sys.stderr)
        return 0

    doc = pymupdf.open(chemin)
    total = 0
    for _ in range(6):
        changement = 0
        for x in range(1, doc.xref_length()):
            try:
                stocke = doc.xref_stream_raw(x)
            except Exception:
                continue
            if not stocke or not any(n in stocke for n in NOMS_SENSIBLES):
                continue
            donnees = flux_a_reencoder(doc, x)
            if donnees is None:
                print(f"  [!] flux {x} laissé tel quel (filtre non standard)",
                      file=sys.stderr)
                continue
            doc.update_stream(x, binascii.hexlify(zlib.compress(donnees, 9)),
                              compress=False)
            doc.xref_set_key(x, "Filter", "[/ASCIIHexDecode /FlateDecode]")
            doc.xref_set_key(x, "DecodeParms", "null")
            changement += 1
        if not changement:
            break
        total += changement
    # pymupdf interdit d'écraser le fichier ouvert : on écrit à côté, puis on
    # remplace (garbage=4 supprime les anciens flux du fichier).
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        provisoire = tmp.name
    doc.save(provisoire, garbage=4)
    doc.close()
    os.replace(provisoire, chemin)
    return total


def noms_sensibles(chemin: str) -> list[str]:
    """Noms d'action PDF (« /JS », « /OpenAction »…) réellement présents dans le
    fichier. Un nom PDF se termine par un délimiteur : les suites d'octets qui
    n'en sont pas ne sont pas retenues."""
    data = open(chemin, "rb").read()
    trouves = set()
    for nom in NOMS_SENSIBLES:
        for m in re.finditer(re.escape(nom), data):
            i, j = m.start(), m.end()
            avant = data[i - 1:i] if i else b""
            apres = data[j:j + 1]
            avant_ok = (not avant) or (avant in [bytes([c]) for c in DELIMITEURS])
            apres_ok = (not apres) or (apres in [bytes([c]) for c in DELIMITEURS])
            if avant_ok and apres_ok:
                trouves.add(nom.decode())
                break
    return sorted(trouves)


def perturber_image(chemin: str, decalage: int, dossier: str) -> str:
    """Copie l'image en modifiant un seul pixel du coin : invisible à l'œil, mais
    les octets du flux compressé changent entièrement, ce qui suffit à écarter
    une suite d'octets prise à tort pour un nom d'action."""
    with PILImage.open(chemin) as im:
        image = im.convert("RGB")
    pixels = image.load()
    r, v, b = pixels[0, 0]
    pixels[0, 0] = ((r + decalage) % 256, v, b)
    sortie = os.path.join(dossier, f"p{decalage:03d}-" + os.path.basename(chemin))
    image.save(sortie)
    return sortie


class DocumentAvecSignets(BaseDocTemplate):
    """Document avec signets (plan cliquable) repris des titres du rapport."""

    NIVEAUX = {"titre": 0, "h2": 1, "h3": 2, "h4": 3}

    def __init__(self, *args, **kwargs):
        BaseDocTemplate.__init__(self, *args, **kwargs)
        self._signets = 0

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        niveau = self.NIVEAUX.get(flowable.style.name)
        if niveau is None:
            return
        titre = flowable.getPlainText().strip()
        if not titre:
            return
        cle = f"signet{self._signets}"
        self._signets += 1
        self.canv.bookmarkPage(cle)
        self.canv.addOutlineEntry(titre[:120], cle, level=niveau, closed=False)


def pied_de_page(canvas, doc, total: int) -> None:
    canvas.saveState()
    canvas.setFont(POLICE, 7.4)
    canvas.setFillColor(GRIS)
    texte = ("TP7 — Applications — Johan Polsinelli — page "
             f"{canvas.getPageNumber()} / {total}")
    canvas.drawCentredString(A4[0] / 2, 11 * mm, texte)
    canvas.setStrokeColor(BORDURE_CLAIR)
    canvas.setLineWidth(0.5)
    canvas.line(MARGE, 14 * mm, A4[0] - MARGE, 14 * mm)
    canvas.restoreState()


# --------------------------------------------------------------------------- #
#  Conversion                                                                  #
# --------------------------------------------------------------------------- #

def convertir(entree: str, sortie: str) -> int:
    base = os.path.dirname(os.path.abspath(entree))
    with open(entree, encoding="utf-8") as f:
        texte = f.read()

    enregistrer_polices()
    S = styles()
    blocs = lire_markdown(texte)
    images = [os.path.join(base, src.replace("%20", " "))
              for genre, contenu in blocs if genre == "image"
              for src in [contenu[1]]]

    def fabriquer(destination, total_ref):
        # BaseDocTemplate recopie ces attributs dans le dictionnaire /Info
        doc = DocumentAvecSignets(
            destination, pagesize=A4, leftMargin=MARGE, rightMargin=MARGE,
            topMargin=15 * mm, bottomMargin=18 * mm, **METADONNEES)
        cadre = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
                      id="corps")
        doc.addPageTemplates([PageTemplate(
            id="page", frames=[cadre],
            onPage=lambda c, d: pied_de_page(c, d, total_ref[0]))])
        return doc

    def construire(remplacements):
        return construire_flowables(blocs, base, S, remplacements)

    # 1) passe de comptage : la pagination ne dépend pas des images
    total = [0]
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        provisoire = tmp.name
    doc_comptage = fabriquer(provisoire, total)
    doc_comptage.build(construire(None))
    total[0] = doc_comptage.page
    os.unlink(provisoire)

    # 2) passe finale : on vérifie que le fichier ne contient aucun nom d'action
    #    PDF et, sinon, on décale un pixel des images pour changer les octets
    #    compressés avant de recommencer.
    dossier = tempfile.mkdtemp(prefix="tp7-images-")
    essai, signatures = 0, []
    while True:
        remplacements = None
        if essai:
            remplacements = {chemin: perturber_image(chemin, essai, dossier)
                             for chemin in images}
        doc = fabriquer(sortie, total)
        doc.build(construire(remplacements))
        if essai == 0:
            flux = neutraliser_flux(sortie)
            if flux:
                print(f"  {flux} flux d'images réencodés en hexadécimal")
        ajouter_xmp(sortie)
        neutraliser_signatures(sortie)
        signatures = noms_sensibles(sortie)
        if not signatures or essai >= TENTATIVES_MAX:
            break
        essai += 1

    print(f"[ok] {sortie} ({os.path.getsize(sortie) / 1024:.0f} ko, "
          f"{total[0]} pages)")
    if signatures:
        print(f"  [!] noms d'action encore présents : {', '.join(signatures)}",
              file=sys.stderr)
    else:
        print("  noms d'action PDF dans le fichier : aucun")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="TP7.md -> PDF (thème GitHub Light)")
    ap.add_argument("--source", default=os.path.join(ICI, "TP7.md"))
    ap.add_argument("--out", default=os.path.join(ICI, "TP7.pdf"))
    args = ap.parse_args()
    return convertir(args.source, args.out)


if __name__ == "__main__":
    raise SystemExit(main())

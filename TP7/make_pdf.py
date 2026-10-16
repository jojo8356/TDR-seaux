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


def construire_flowables(blocs, base: str, S: dict) -> list:
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
            flux.append(image_flowable(chemin, LARGEUR_UTILE,
                                        HAUTEUR_IMAGE_MAX))
            flux.append(Spacer(1, 2))
            if legende:
                flux.append(Paragraph(f"<i>{en_ligne(legende)}</i>", S["legende"]))
            flux.append(Spacer(1, 9))
    return flux


# --------------------------------------------------------------------------- #
#  Pagination                                                                  #
# --------------------------------------------------------------------------- #

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

    def flux():
        """Les flowables reportlab sont consommés par une passe : on les
        reconstruit pour la seconde."""
        return construire_flowables(blocs, base, S)

    # une première passe pour compter les pages, une seconde pour écrire
    # « page X / Y »
    import tempfile

    def fabriquer(destination):
        doc = BaseDocTemplate(destination, pagesize=A4, leftMargin=MARGE,
                              rightMargin=MARGE, topMargin=15 * mm,
                              bottomMargin=18 * mm, title="TP7 — Applications",
                              author="Johan Polsinelli")
        cadre = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
                      id="corps")
        doc.addPageTemplates([PageTemplate(
            id="page", frames=[cadre],
            onPage=lambda c, d: pied_de_page(c, d, total_pages[0]))])
        return doc

    total_pages = [0]
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        provisoire = tmp.name
    doc_provisoire = fabriquer(provisoire)
    doc_provisoire.build(flux())
    total_pages[0] = doc_provisoire.page

    doc = fabriquer(sortie)
    doc.build(flux())
    total = total_pages[0]
    os.unlink(provisoire)
    print(f"[ok] {sortie} ({os.path.getsize(sortie) / 1024:.0f} ko, "
          f"{total} pages)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="TP7.md -> PDF (thème GitHub Light)")
    ap.add_argument("--source", default=os.path.join(ICI, "TP7.md"))
    ap.add_argument("--out", default=os.path.join(ICI, "TP7.pdf"))
    args = ap.parse_args()
    return convertir(args.source, args.out)


if __name__ == "__main__":
    raise SystemExit(main())

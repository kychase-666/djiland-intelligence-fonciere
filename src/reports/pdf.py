"""
Rapport d'évaluation foncière PROFESSIONNEL (livrable vendable).

Agrège l'ensemble de l'intelligence Djiland pour une parcelle en un dossier
PDF multi-sections : synthèse & verdict, localisation, évaluation financière,
trajectoire de valeur (−5 → +5 ans), environnement & risques, spéculation,
transport & infrastructures futures, sécurité juridique + checklist documents.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone

from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Palette Djiland
VERT = colors.HexColor("#1F6F5C")
VERT_FONCE = colors.HexColor("#123c33")
OR = colors.HexColor("#C8A04B")
ROUGE = colors.HexColor("#dc2626")
ORANGE = colors.HexColor("#f59e0b")
VERT_OK = colors.HexColor("#16a34a")
GRIS = colors.HexColor("#EEECE6")

_STYLES = getSampleStyleSheet()
H_SECTION = ParagraphStyle("sec", parent=_STYLES["Heading2"], textColor=colors.white,
                           fontSize=12, leading=15, spaceAfter=0, leftIndent=6)
P = ParagraphStyle("p", parent=_STYLES["Normal"], fontSize=9, leading=13)
P_SMALL = ParagraphStyle("ps", parent=_STYLES["Normal"], fontSize=7.5, leading=10,
                         textColor=colors.HexColor("#555555"))


def _fmt(v, suffix=""):
    """Formate proprement une valeur numérique (séparateur de milliers)."""
    if v is None:
        return "—"
    if isinstance(v, (int, float)):
        return f"{v:,.0f}{suffix}".replace(",", " ")
    return f"{v}{suffix}"


def _section(titre: str, couleur=VERT):
    """Barre de titre de section colorée (Table 1 cellule)."""
    t = Table([[Paragraph(titre, H_SECTION)]], colWidths=[17 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), couleur),
                           ("TOPPADDING", (0, 0), (-1, -1), 5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t


def _kv(pairs, col1=8.5, col2=8.5):
    """Table clé/valeur à deux colonnes."""
    data = [[Paragraph(f"<b>{k}</b>", P), Paragraph(str(v), P)] for k, v in pairs]
    t = Table(data, colWidths=[col1 * cm, col2 * cm])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#DDDDDD")),
        ("BACKGROUND", (0, 0), (0, -1), GRIS),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6)]))
    return t


def _verdict(d: dict, dist_transport: float | None) -> tuple:
    """Calcule le verdict global (libellé, couleur, justification).

    Délègue à opportunites.score_ligne : même verdict que le Chasseur
    d'opportunités du dashboard.
    """
    from src.analysis.opportunites import VERDICTS, score_ligne

    score, cle = score_ligne(d, dist_transport)
    libelle, _, justif = VERDICTS[cle]
    couleur = {"evite": ROUGE, "forte": VERT_OK, "interessant": VERT,
               "prudence": ORANGE, "faible": ROUGE}[cle]
    if cle != "evite":
        justif = f"{justif} Score d'opportunité : {score:.0f}/100."
    return (libelle, couleur, justif)


def _traj_chart(traj: list[dict]) -> Drawing:
    """Graphe de la trajectoire de valeur (−5 → +5 ans)."""
    d = Drawing(460, 170)
    lc = HorizontalLineChart()
    lc.x, lc.y, lc.width, lc.height = 35, 25, 410, 125
    lc.data = [[t["prix_total"] for t in traj]]
    lc.categoryAxis.categoryNames = [str(t["annee"]) for t in traj]
    lc.categoryAxis.labels.fontSize = 7
    lc.valueAxis.valueMin = 0
    lc.valueAxis.labels.fontSize = 6
    lc.lines[0].strokeColor = VERT
    lc.lines[0].strokeWidth = 2.2
    lc.lines.symbol = None
    d.add(lc)
    return d


def _header_footer(canvas, doc):
    """En-tête et pied de page sur chaque page."""
    canvas.saveState()
    canvas.setFillColor(VERT_FONCE)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(2 * cm, A4[1] - 1.1 * cm, "DJILAND SARL")
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#888888"))
    canvas.drawRightString(A4[0] - 2 * cm, A4[1] - 1.1 * cm,
                           "Intelligence Foncière — Rapport d'évaluation")
    canvas.setStrokeColor(OR)
    canvas.line(2 * cm, A4[1] - 1.3 * cm, A4[0] - 2 * cm, A4[1] - 1.3 * cm)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(2 * cm, 1 * cm, "Document confidentiel — usage interne Djiland SARL.")
    canvas.drawRightString(A4[0] - 2 * cm, 1 * cm, f"Page {doc.page}")
    canvas.restoreState()


def build_full_report(d: dict, output_path: str | None = None) -> bytes:
    """Génère le rapport PDF professionnel complet d'une parcelle.

    Args:
        d: dictionnaire de la parcelle enrichie (tous champs), incluant lon, lat,
           surface_m2, prix_m2_fcfa et les couches avancées/juridiques.
        output_path: si fourni, écrit aussi le PDF sur disque.

    Returns:
        Le PDF sérialisé en bytes.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.7 * cm, bottomMargin=1.5 * cm,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            title=f"Rapport {d.get('code_parcelle', '')}")
    story = []

    # Évaluation temporelle + transport
    try:
        from src.analysis.evaluation import distance_future_transport_km, evaluate
        surface = float(d.get("surface_m2", 500) or 500)
        prix_m2 = float(d.get("prix_m2_fcfa", 0) or 0)
        ev = evaluate(d.get("commune", ""), prix_m2, surface,
                      heat=float(d.get("speculation_heat", 50) or 50),
                      lon=d.get("lon"), lat=d.get("lat"))
        dist_transport = (distance_future_transport_km(d["lon"], d["lat"])
                          if d.get("lon") is not None else None)
    except Exception:
        ev, dist_transport, surface, prix_m2 = None, None, float(d.get("surface_m2", 500) or 500), 0

    # --- Titre ---
    story.append(Paragraph("RAPPORT D'ÉVALUATION FONCIÈRE",
                           ParagraphStyle("t", parent=_STYLES["Title"], textColor=VERT_FONCE,
                                          fontSize=20)))
    story.append(Paragraph(
        f"Parcelle <b>{d.get('code_parcelle', '—')}</b> · {d.get('commune', '—')} · "
        f"généré le {datetime.now(timezone.utc):%d/%m/%Y}",
        ParagraphStyle("st", parent=_STYLES["Normal"], fontSize=10, alignment=TA_CENTER,
                       textColor=colors.HexColor("#666"))))
    story.append(Spacer(1, 0.35 * cm))

    # --- Verdict ---
    libelle, coul, justif = _verdict(d, dist_transport)
    vt = Table([[Paragraph(f"<b>{libelle}</b>",
                           ParagraphStyle("v", parent=_STYLES["Normal"], fontSize=15,
                                          textColor=colors.white, alignment=TA_CENTER))],
                [Paragraph(justif, ParagraphStyle("vj", parent=_STYLES["Normal"], fontSize=9,
                                                  textColor=colors.white, alignment=TA_CENTER))]],
               colWidths=[17 * cm])
    vt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), coul),
                            ("TOPPADDING", (0, 0), (-1, -1), 7),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story += [vt, Spacer(1, 0.4 * cm)]

    # --- 1. Évaluation financière ---
    fourchette = (f"{_fmt(prix_m2 * 0.85 * surface)} – {_fmt(prix_m2 * 1.15 * surface)} FCFA"
                  if prix_m2 else "—")
    story += [_section("1 · Évaluation financière"), Spacer(1, 0.15 * cm),
              _kv([("Surface", _fmt(surface, " m²")),
                   ("Prix estimé au m²", _fmt(prix_m2, " FCFA")),
                   ("Valeur totale estimée", _fmt(prix_m2 * surface, " FCFA")),
                   ("Fourchette de valeur", fourchette),
                   ("Rendement locatif brut estimé", _fmt(d.get("rendement_locatif"), " %"))]),
              Spacer(1, 0.35 * cm)]

    # --- 2. Trajectoire de valeur ---
    if ev:
        t = {r["horizon"]: r["prix_total"] for r in ev["trajectoire"]}
        story += [_section("2 · Trajectoire de valeur (passé → futur)"), Spacer(1, 0.1 * cm),
                  _kv([("Valeur il y a 5 ans", _fmt(t.get(-5), " FCFA")),
                       ("Valeur aujourd'hui", _fmt(t.get(0), " FCFA")),
                       ("Valeur projetée à 5 ans", _fmt(t.get(5), " FCFA")),
                       ("Taux annuel (passé → futur)",
                        f"{ev['taux_annuel_passe']} % → {ev['taux_annuel_futur']} %/an")]),
                  Spacer(1, 0.1 * cm), _traj_chart(ev["trajectoire"]),
                  Paragraph("Projection spéculative NON garantie — modèle borné et décélérant.",
                            P_SMALL), Spacer(1, 0.3 * cm)]

    # --- 3. Transport & infrastructures futures ---
    dt = (f"{dist_transport} km d'un projet de transport futur"
          if dist_transport is not None and dist_transport < 90 else "aucun projet à proximité")
    story += [_section("3 · Transport & infrastructures futures"), Spacer(1, 0.15 * cm),
              _kv([("Accessibilité au Plateau", _fmt(d.get("accessibilite_min"), " min")),
                   ("Distance au Plateau", _fmt(d.get("dist_plateau_km"), " km")),
                   ("Proximité transport futur", dt),
                   ("Prime de valorisation transport",
                    _fmt(ev["prime_transport_pts"], " pts/an") if ev else "—")]),
              Spacer(1, 0.35 * cm)]

    # --- 4. Environnement & risques ---
    nuis = (f"malus −{(d.get('malus_nuisance', 0) or 0) * 100:.0f} % (nuisance à "
            f"{_fmt(d.get('dist_nuisance_m'), ' m')})" if (d.get("malus_nuisance", 0) or 0) > 0.05
            else "aucune nuisance majeure à proximité")
    story += [_section("4 · Environnement & risques"), Spacer(1, 0.15 * cm),
              _kv([("Couvert végétal (NDVI)", _fmt(d.get("ndvi_moyen"))),
                   ("Pente moyenne", _fmt(d.get("pente_moyenne_deg"), " °")),
                   ("Risque d'inondation (0-1)", _fmt(d.get("risque_inondation"))),
                   ("Vue lagune", "OUI (prime de valeur)" if d.get("vue_lagune") else "non"),
                   ("Nuisances (NIMBY)", nuis)]),
              Spacer(1, 0.35 * cm)]

    # --- 5. Spéculation ---
    story += [_section("5 · Signaux spéculatifs"), Spacer(1, 0.15 * cm),
              _kv([("Speculation Heat Index", _fmt(d.get("speculation_heat"), " / 100")),
                   ("Indice de convoitise", _fmt(d.get("convoitise"), " / 100")),
                   ("Chantier détecté (satellite)", "OUI" if d.get("chantier_detecte") else "non"),
                   ("Vallée de rattrapage (signal d'achat)",
                    "OUI" if d.get("rattrapage") else "non")]),
              Spacer(1, 0.35 * cm)]

    # --- 6. Sécurité juridique ---
    statut = d.get("lotissement_statut", "—")
    story += [_section("6 · Sécurité juridique (à vérifier officiellement)", VERT_FONCE),
              Spacer(1, 0.15 * cm),
              _kv([("Lotissement", d.get("lotissement_nom", "—")),
                   ("Statut d'approbation", f"{statut} (démo)"),
                   ("Identifiant IDUFCI (démo)", d.get("idufci_demo", "—")),
                   ("ACD / concession définitive", "oui" if d.get("acd") else "non"),
                   ("Titre foncier", "oui" if d.get("titre_foncier") else "non"),
                   ("Litige connu", "OUI" if d.get("litige_parcelle") else "non"),
                   ("Score de sécurité juridique", _fmt(d.get("score_juridique"), " / 100")),
                   ("Propriétaire", "à vérifier — État Foncier DGI (3 000 FCFA)")]),
              Spacer(1, 0.2 * cm)]

    # Checklist documents
    try:
        from src.analysis.juridique import documents_a_exiger
        docs = documents_a_exiger(statut)
        story.append(Paragraph("<b>Documents à exiger du vendeur :</b>", P))
        for doc_ in docs:
            clean = "".join(c for c in doc_ if ord(c) < 0x2500)  # retire les emojis
            story.append(Paragraph(f"• {clean.strip()}", P))
    except Exception:
        pass

    # --- Disclaimer ---
    story += [Spacer(1, 0.4 * cm), HRFlowable(width="100%", color=OR, thickness=1),
              Spacer(1, 0.15 * cm),
              Paragraph(
                  "AVERTISSEMENT : rapport indicatif produit par le système d'intelligence "
                  "foncière Djiland. Les prix, projections, scores et données juridiques "
                  "(statut de lotissement, IDUFCI) sont estimés/calibrés et, pour certains, "
                  "des données de DÉMONSTRATION. Ils ne se substituent pas à une expertise "
                  "terrain, une vérification cadastrale (IDUFCI/DGI/MCLU) ni à un acte notarié. "
                  "Aucune garantie de valeur future.", P_SMALL)]

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    pdf = buf.getvalue()
    if output_path:
        with open(output_path, "wb") as f:
            f.write(pdf)
    return pdf


def build_report(parcelle: dict, output_path: str | None = None) -> bytes:
    """Compatibilité : redirige vers le rapport professionnel complet."""
    return build_full_report(parcelle, output_path)

"""
gerar_pdf_teste.py — cria um PDF sintético que imita o layout CDA
para validar o extrator sem precisar de um documento real.

Execute:  python gerar_pdf_teste.py
Gera:     teste_cda.pdf
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm


def _estilo_cabecalho():
    estilos = getSampleStyleSheet()
    return ParagraphStyle(
        "Cabecalho",
        parent=estilos["Normal"],
        fontSize=11,
        fontName="Helvetica-Bold",
        alignment=1,   # centro
        spaceAfter=6,
    )


def _bloco_cda(inscricao: str, registros: list[tuple]) -> list:
    """
    Gera os elementos para um bloco CDA:
      - tabela de Inscrição
      - título "CERTIDÃO DE DÍVIDA ATIVA"
      - tabela de Referência / Nº CDA / Situação
    """
    estilo_titulo = _estilo_cabecalho()
    elementos = []

    # Tabela Inscrição
    t_inscricao = Table(
        [["Inscrição"], [inscricao]],
        colWidths=[5 * cm],
        hAlign="LEFT",
    )
    t_inscricao.setStyle(TableStyle([
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND",  (0, 0), (-1, 0),  colors.lightgrey),
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("ALIGN",       (0, 0), (-1, -1), "LEFT"),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elementos.append(t_inscricao)
    elementos.append(Spacer(1, 0.4 * cm))

    # Título
    elementos.append(Paragraph("CERTIDÃO DE DÍVIDA ATIVA", estilo_titulo))
    elementos.append(Spacer(1, 0.2 * cm))

    # Tabela principal
    dados = [["Referência", "Nº da C.D.A", "Situação"]] + list(registros)
    t_cda = Table(
        dados,
        colWidths=[8 * cm, 5 * cm, 4 * cm],
        hAlign="LEFT",
    )
    t_cda.setStyle(TableStyle([
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND",  (0, 0), (-1, 0),  colors.lightgrey),
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("ALIGN",       (0, 0), (-1, -1), "LEFT"),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elementos.append(t_cda)
    elementos.append(Spacer(1, 0.8 * cm))

    return elementos


def gerar_pdf(caminho: str = "teste_cda.pdf"):
    doc = SimpleDocTemplate(
        caminho,
        pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm,  bottomMargin=2 * cm,
    )

    elementos = []

    # --- Página 1: contribuinte com IPTU e TCR ---
    elementos += _bloco_cda(
        inscricao="163895-5",
        registros=[
            ("IPTU - CDA (CDA)",    "2023.001.00001-0", "Ativo(a)"),
            ("TCR - CDA (Dívida)",  "2023.001.00002-8", "Ativo(a)"),
        ]
    )

    # Segundo contribuinte na mesma página
    elementos += _bloco_cda(
        inscricao="298741-2",
        registros=[
            ("IPTU - CDA (CDA)",    "2022.003.04512-1", "Ativo(a)"),
        ]
    )

    # --- Quebra de página ---
    from reportlab.platypus import PageBreak
    elementos.append(PageBreak())

    # --- Página 2: outro contribuinte ---
    elementos += _bloco_cda(
        inscricao="407332-0",
        registros=[
            ("IPTU - CDA (CDA)",    "2021.002.09981-7", "Ativo(a)"),
            ("TCR - CDA (Dívida)",  "2021.002.09982-5", "Ativo(a)"),
            ("IPTU - CDA (CDA)",    "2020.002.07761-3", "Ativo(a)"),
        ]
    )

    doc.build(elementos)
    print(f"PDF de teste gerado: {caminho}")


if __name__ == "__main__":
    gerar_pdf()

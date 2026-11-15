# services/gerador_pdf.py
import io
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

def gerar_pdf_saldo(romaneios, total_ton, total_valor, logo_filename=None):
    """
    Gera o PDF do saldo pendente (paisagem A4).
    - romaneios: lista de objetos Romaneio
    - total_ton: soma das toneladas excedentes
    - total_valor: soma dos valores a receber
    - logo_filename: nome do arquivo salvo em static/img/
    """
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=1 * cm,
        leftMargin=1 * cm,
        topMargin=1 * cm,
        bottomMargin=1 * cm,
    )
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name='TitleCustom', parent=styles['Heading1'],
        alignment=1, fontSize=16, spaceAfter=6
    )
    sub_style = ParagraphStyle(
        name='SubCustom', parent=styles['Normal'],
        alignment=1, fontSize=11, textColor=colors.HexColor("#475569")
    )
    normal_style = styles['Normal']

    # --- LOGO (opcional) ---
    if logo_filename:
        caminho_logo = os.path.join('static', 'img', logo_filename)
        if os.path.exists(caminho_logo):
            try:
                img = Image(caminho_logo, width=4 * cm, height=2 * cm, kind='proportional')
                elements.append(img)
                elements.append(Spacer(1, 8))
            except Exception as e:
                print(f"[PDF] Erro ao carregar logo: {e}")

    # --- CABEÇALHO ---
    elements.append(Paragraph("FBE FAST BIOMASS X QUEIROZ - 5.122", title_style))
    elements.append(Paragraph(
        "Relatório de Acerto de Peso e Saldo Pendente",
        sub_style
    ))
    elements.append(Spacer(1, 16))

    # --- TABELA ---
    data = [[
        'Romaneio', 'Data', 'Placa', 'Motorista',
        'Peso Fisco (t)', 'Peso Real (t)', 'Diferença (t)', 'Valor a Receber (R$)'
    ]]

    for r in romaneios:
        data.append([
            str(r.numero_romaneio or '-'),
            r.data_criacao.strftime('%d/%m/%Y') if r.data_criacao else '-',
            r.conjunto.placa_tracionador if r.conjunto else '-',
            (r.motorista.nome if r.motorista else '-')[:30],
            f"{r.peso_fisco:.2f}" if r.peso_fisco else '0.00',
            f"{r.peso_real:.3f}" if r.peso_real else '0.000',
            f"{r.dif_peso:.3f}",
            f"R$ {r.dif_valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
        ])

    # Linha de total
    data.append([
        'TOTAL', '', '', '', '', '',
        f"{total_ton:.3f}",
        f"R$ {total_valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
    ])

    table = Table(
        data,
        colWidths=[2.2*cm, 2.2*cm, 2.4*cm, 4.5*cm, 2.4*cm, 2.4*cm, 2.4*cm, 3.8*cm],
        repeatRows=1,
    )

    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -2), 8),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E2E8F0")),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#94A3B8")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor("#F8FAFC")]),
    ])
    table.setStyle(style)

    elements.append(table)
    elements.append(Spacer(1, 16))
    elements.append(Paragraph(
        "Este relatório refere-se apenas aos romaneios <b>pendentes de acerto</b>. "
        "Os romaneios já faturados não aparecem nesta lista.",
        normal_style
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer
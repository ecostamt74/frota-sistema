import io
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

def gerar_pdf_saldo(romaneios, total_ton, total_valor, logo_filename='logo_padrao.png'):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=0.5*cm, leftMargin=0.5*cm, topMargin=0.5*cm, bottomMargin=0.5*cm)
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name='Title', parent=styles['Heading1'], alignment=1, fontSize=14, spaceAfter=10)
    normal_style = styles['Normal']

    # Logo (se existir)
    caminho_logo = os.path.join('static', 'img', logo_filename)
    if os.path.exists(caminho_logo):
        try:
            img = Image(caminho_logo, width=3*cm, height=1.5*cm, kind='proportional')
            elements.append(img)
        except: pass

    elements.append(Paragraph("FBE FAST BIOMASS X QUEIROZ - CONTRATO 5.122", title_style))
    elements.append(Paragraph("Relatório de Acerto de Peso e Saldo Pendente", ParagraphStyle(name='Sub', parent=normal_style, alignment=1, fontSize=10)))
    elements.append(Spacer(1, 10))

    # Cabeçalho Lado a Lado
    data = [
        ['NF FISCO', '', '', '', '', '', '', 'DESCARGAS', '', '', '', ''],
        ['QTD', 'DATA', 'PLACA', 'NOTA', 'TON', 'VALOR/TON', 'VALOR NF', 'TON. ENTREGUE', 'VALOR/TON', 'TOTAL', 'DIF FISCO', 'DIF VALOR']
    ]

    for i, r in enumerate(romaneios, 1):
        data.append([
            str(i), 
            r.data_criacao.strftime('%d/%m/%Y') if r.data_criacao else '-',
            r.conjunto.placa_tracionador if r.conjunto else '-',
            r.numero_nota_original or '-',
            f"{r.peso_fisco:.2f}",
            f"R$ {r.valor_tonelada:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            f"R$ {(r.peso_fisco * r.valor_tonelada):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            f"{r.peso_real:.3f}" if r.peso_real else '0.000',
            f"R$ {r.valor_tonelada:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            f"R$ {((r.peso_real or 0) * r.valor_tonelada):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            f"{r.dif_peso:.3f}",
            f"R$ {r.dif_valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        ])

    # Linha de Total
    data.append([
        'TOTAL', '', '', '', '', '', '', '', '', '', 
        f"{total_ton:.3f}", 
        f"R$ {total_valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    ])

    table = Table(data, colWidths=[0.8*cm, 1.8*cm, 1.8*cm, 1.2*cm, 1.2*cm, 1.5*cm, 2.2*cm, 1.5*cm, 1.5*cm, 2.2*cm, 1.5*cm, 2.2*cm], repeatRows=2)
    
    style = TableStyle([
        ('BACKGROUND', (0, 0), (6, 0), colors.HexColor("#1F4E78")), # Azul Escuro Fisco
        ('BACKGROUND', (7, 0), (11, 0), colors.HexColor("#2E75B6")), # Azul Claro Descargas
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('SPAN', (0, 0), (6, 0)),
        ('SPAN', (7, 0), (11, 0)),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 1), 8),
        ('FONTSIZE', (0, 2), (-1, -2), 7),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E2E8F0")),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0, 2), (-1, -2), [colors.white, colors.HexColor("#F8FAFC")]),
    ])
    table.setStyle(style)

    elements.append(table)
    elements.append(Spacer(1, 15))
    elements.append(Paragraph("Este relatório refere-se apenas aos romaneios pendentes de acerto.", normal_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer
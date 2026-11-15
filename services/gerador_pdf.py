import io
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

def gerar_pdf_saldo(romaneios, total_ton, total_valor, logo_filename):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=1*cm, leftMargin=1*cm, topMargin=1*cm, bottomMargin=1*cm)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name='Title', parent=styles['Heading1'], alignment=1, fontSize=16, spaceAfter=20)
    normal_style = styles['Normal']
    
    if logo_filename:
        caminho_logo = os.path.join('static', 'img', logo_filename)
        if os.path.exists(caminho_logo):
            try:
                img = Image(caminho_logo, width=4*cm, height=2*cm, kind='proportional')
                elements.append(img)
                elements.append(Spacer(1, 10))
            except Exception as e:
                print(f"Erro ao carregar logo: {e}")

    elements.append(Paragraph("FBE FAST BIOMASS X QUEIROZ - 5.122", title_style))
    elements.append(Paragraph("Relatório de Acerto de Peso e Saldo Pendente", ParagraphStyle(name='Sub', parent=normal_style, alignment=1, fontSize=12)))
    elements.append(Spacer(1, 20))
    
    data = [['Romaneio', 'Data', 'Placa', 'Motorista', 'Peso Fisco (t)', 'Peso Real (t)', 'Diferença (t)', 'Valor a Receber (R$)']]
    for r in romaneios:
        data.append([
            r.numero_romaneio,
            r.data_criacao.strftime('%d/%m/%Y') if r.data_criacao else '-',
            r.conjunto.placa_tracionador if r.conjunto else '-',
            r.motorista.nome if r.motorista else '-',
            f"{r.peso_fisco:.2f}",
            f"{r.peso_real:.3f}" if r.peso_real else '0.000',
            f"{r.dif_peso:.3f}",
            f"R$ {r.dif_valor:.2f}"
        ])
    data.append(['TOTAL', '', '', '', '', '', f"{total_ton:.3f}", f"R$ {total_valor:.2f}"])
    
    table = Table(data, colWidths=[2.5*cm, 2.5*cm, 2.5*cm, 5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 3.5*cm])
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E2E8F0")),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ])
    table.setStyle(style)
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Este relatório refere-se apenas aos romaneios pendentes de acerto.", normal_style))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer
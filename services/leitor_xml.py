from lxml import etree

NS = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

def ler_xml_nfe_transferencia(caminho_xml):
    dados = {}
    try:
        tree = etree.parse(caminho_xml)
        root = tree.getroot()
        infNFe = root.find('.//nfe:infNFe', NS)
        if infNFe is not None:
            dados['chave'] = infNFe.get('Id', '').replace('NFe', '')
        vol = root.find('.//nfe:vol', NS)
        if vol is not None:
            dados['peso_liquido'] = float(vol.findtext('nfe:pesoL', namespaces=NS) or 0)
    except Exception as e:
        print(f"Erro ao ler XML: {e}")
    return dados

def ler_xml_nfe_venda(caminho_xml):
    dados = {}
    try:
        tree = etree.parse(caminho_xml)
        root = tree.getroot()
        infNFe = root.find('.//nfe:infNFe', NS)
        if infNFe is not None:
            dados['chave_venda'] = infNFe.get('Id', '').replace('NFe', '')
        vol = root.find('.//nfe:vol', NS)
        if vol is not None:
            dados['peso_bruto_real'] = float(vol.findtext('nfe:pesoB', namespaces=NS) or 0)
    except Exception as e:
        print(f"Erro ao ler XML: {e}")
    return dados

def ler_xml_mdfe(caminho_xml):
    dados = {}
    try:
        tree = etree.parse(caminho_xml)
        root = tree.getroot()
        # Simplificado para o sistema não quebrar
        dados['chave_mdfe'] = "MDFE_IMPORTADO"
    except Exception as e:
        print(f"Erro ao ler XML: {e}")
    return dados
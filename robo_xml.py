import os
import time
import shutil
import glob
from app import app, db
from models import Romaneio, MovimentoEstoque
from services.leitor_xml import ler_xml_nfe_transferencia, ler_xml_nfe_venda

PASTA_ENTRADA = 'entrada_xml'
PASTA_PROCESSADOS = 'entrada_xml/processados'
os.makedirs(PASTA_PROCESSADOS, exist_ok=True)

def classificar_e_importar(caminho_xml):
    nome_arquivo = os.path.basename(caminho_xml)
    print(f"Lendo arquivo: {nome_arquivo}")
    
    with app.app_context():
        dados = ler_xml_nfe_venda(caminho_xml)
        if dados.get('chave_venda'):
            print(f" -> Venda detectada! Chave: {dados['chave_venda']}")
        
        shutil.move(caminho_xml, os.path.join(PASTA_PROCESSADOS, nome_arquivo))
        print(f" -> Arquivo movido para processados.")

def vigiar_pasta():
    print("🤖 Robô iniciado! Monitorando a pasta 'entrada_xml'...")
    while True:
        arquivos = glob.glob(os.path.join(PASTA_ENTRADA, '*.xml'))
        for arquivo in arquivos:
            try:
                classificar_e_importar(arquivo)
            except Exception as e:
                print(f"❌ Erro ao processar {arquivo}: {e}")
        time.sleep(5)

if __name__ == '__main__':
    vigiar_pasta()
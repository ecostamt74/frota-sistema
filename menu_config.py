# menu_config.py
# Estrutura reorganizada por grupos lógicos (Melhor Prática B2B)

MENUS = [
    # --- GRUPO: OPERAÇÃO ---
    {"titulo": "📊 Painel", "endpoint": "index", "ativo": True, "perfil": "todos", "grupo": "Operação"},
    {"titulo": "📈 Dashboard", "endpoint": "dashboard", "ativo": True, "perfil": "todos", "grupo": "Operação"},

    # --- GRUPO: CADASTROS (Dados Mestres) ---
    {"titulo": "👤 Motoristas", "endpoint": "listar_motoristas", "ativo": True, "perfil": "todos", "grupo": "Cadastros"},
    {"titulo": "🚛 Caminhões", "endpoint": "listar_caminhoes", "ativo": True, "perfil": "todos", "grupo": "Cadastros"},
    {"titulo": "🏢 Empresas", "endpoint": "listar_empresas", "ativo": True, "perfil": "admin", "grupo": "Cadastros"},

    # --- GRUPO: MOVIMENTAÇÃO (Operação Diária) ---
    {"titulo": "⛽ Abastecimentos", "endpoint": "listar_abastecimentos", "ativo": True, "perfil": "todos", "grupo": "Movimentação"},
    {"titulo": "🔧 Manutenções", "endpoint": "listar_manutencoes", "ativo": True, "perfil": "todos", "grupo": "Movimentação"},
    {"titulo": "⚠️ Multas", "endpoint": "listar_multas", "ativo": True, "perfil": "todos", "grupo": "Movimentação"},
    {"titulo": "📄 Notas Fiscais", "endpoint": "upload_nota", "ativo": True, "perfil": "operador", "grupo": "Movimentação"},

    # --- GRUPO: SISTEMA (Configurações e Apoio) ---
    {"titulo": "📥 Importar Excel", "endpoint": "importar_excel", "ativo": True, "perfil": "operador", "grupo": "Sistema"},
    {"titulo": "🔒 LGPD", "endpoint": "lgpd_info", "ativo": True, "perfil": "todos", "grupo": "Sistema"},
]
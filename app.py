import streamlit as st
import google.generativeai as genai
from supabase import create_client
import json
import pandas as pd
from datetime import datetime, date, timedelta

# ==========================================
# CONFIGURAÇÕES INICIAIS E CSS
# ==========================================
st.set_page_config(page_title="Controle Financeiro", page_icon="💸", layout="wide")

esconder_estilos_streamlit = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stHeader"] {display: none !important;}
    [data-testid="stToolbar"] {display: none !important;}
    [data-testid="stDecoration"] {display: none !important;}
    [data-testid="stStatusWidget"] {display: none !important;}
    .stAppDeployButton {display: none !important;}
    a.header-anchor {display: none !important;}
    </style>
"""
st.markdown(esconder_estilos_streamlit, unsafe_allow_html=True)

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)

# ==========================================
# FUNÇÕES DE FORMATAÇÃO E CONVERSÃO
# ==========================================
def formatar_moeda(valor):
    if pd.isna(valor) or valor == "": return "R$ 0,00"
    valor_str = f"{float(valor):,.2f}"
    valor_str = valor_str.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {valor_str}"

def apenas_numero_br(valor):
    if pd.isna(valor) or valor == "": return "0,00"
    valor_str = f"{float(valor):,.2f}"
    return valor_str.replace(",", "X").replace(".", ",").replace("X", ".")

def texto_para_float(valor_str):
    if pd.isna(valor_str) or valor_str is None: return 0.0
    if isinstance(valor_str, (float, int)): return float(valor_str)
    v = str(valor_str).replace("R$", "").strip()
    if not v: return 0.0
    qtd_pontos = v.count(".")
    qtd_virgulas = v.count(",")
    if qtd_pontos > 0 and qtd_virgulas > 0:
        pos_ponto = v.rfind(".")
        pos_virgula = v.rfind(",")
        if pos_virgula > pos_ponto: v = v.replace(".", "").replace(",", ".")
        else: v = v.replace(",", "")
    elif qtd_virgulas == 1 and qtd_pontos == 0: v = v.replace(",", ".")
    elif qtd_pontos > 1 and qtd_virgulas == 0: v = v.replace(".", "")
    elif qtd_virgulas > 1 and qtd_pontos == 0: v = v.replace(",", "")
    try: return float(v)
    except: return 0.0

# ==========================================
# SISTEMA DE LOGIN
# ==========================================
if st.session_state.get('conta_id') is None:
    if "cid" in st.query_params:
        cid_salvo = st.query_params["cid"]
        resp = supabase.table("contas").select("*").eq("id", cid_salvo).execute()
        if resp.data:
            conta = resp.data[0]
            st.session_state['conta_id'] = conta['id']
            st.session_state['nome_1'] = conta['nome_1']
            st.session_state['nome_2'] = conta['nome_2']

if st.session_state.get('conta_id') is None:
    st.title("🔐 Acesso ao Controle Financeiro")
    aba_login, aba_cadastro = st.tabs(["🔑 Fazer Login", "📝 Criar Conta"])
    
    with aba_login:
        usuario_login = st.text_input("Usuário")
        senha_login = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            resp = supabase.table("contas").select("*").eq("usuario", usuario_login).eq("senha", senha_login).execute()
            if resp.data:
                conta = resp.data[0]
                st.session_state['conta_id'] = conta['id']
                st.session_state['nome_1'] = conta['nome_1']
                st.session_state['nome_2'] = conta['nome_2']
                st.query_params["cid"] = str(conta['id'])
                st.success("Login efetuado com sucesso!")
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
                
    with aba_cadastro:
        tipo_conta = st.radio("Como você vai usar o sistema?", ["Em Casal", "Sozinho (Individual)"])
        novo_usuario = st.text_input("Crie um nome de Usuário")
        nova_senha = st.text_input("Crie uma Senha", type="password")
        nome_1 = st.text_input("Seu Nome (Pessoa 1)")
        nome_2 = st.text_input("Nome do Parceiro(a) (Pessoa 2)") if tipo_conta == "Em Casal" else ""
        
        if st.button("Criar Conta"):
            if not novo_usuario or not nova_senha or not nome_1:
                st.warning("Preencha os campos obrigatórios!")
            elif tipo_conta == "Em Casal" and not nome_2:
                st.warning("Preencha o nome da Pessoa 2!")
            else:
                try:
                    supabase.table("contas").insert({
                        "usuario": novo_usuario, "senha": nova_senha,
                        "nome_1": nome_1, "nome_2": nome_2
                    }).execute()
                    st.success("Conta criada! Volte na aba de Login para entrar.")
                except:
                    st.error("Erro ao criar. Esse usuário já existe.")
    st.stop()

# ==========================================
# INTERFACE DO SITE (LOGADO)
# ==========================================
CONTA_ID = st.session_state['conta_id']
NOME_USUARIO_1 = st.session_state['nome_1']
NOME_USUARIO_2 = st.session_state['nome_2']
MODO_CASAL = (NOME_USUARIO_2 != "")
OPCOES_COMPRADOR = [NOME_USUARIO_1, NOME_USUARIO_2, "Juntos (Dividido 50/50)"] if MODO_CASAL else [NOME_USUARIO_1]

with st.sidebar:
    st.write(f"Bem-vindos, **{NOME_USUARIO_1} & {NOME_USUARIO_2}**! 👋" if MODO_CASAL else f"Bem-vinda(o), **{NOME_USUARIO_1}**! 👋")
    if st.button("Sair da Conta"):
        st.query_params.clear()
        st.session_state.clear()
        st.rerun()

st.title("💸 Controle Financeiro")

aba_dashboard, aba_add_manual, aba_renda, aba_pdf, aba_config = st.tabs([
    "📊 Visão e Edição", "✍️ Registrar Compra", "💰 Salários", "📄 Fatura PDF", "⚙️ Categorias e Cartões"
])

# BUSCA DADOS GERAIS
resp_gastos = supabase.table("gastos").select("*").eq("conta_id", CONTA_ID).execute()
resp_rendas = supabase.table("receitas").select("*").eq("conta_id", CONTA_ID).execute()
resp_categorias = supabase.table("categorias").select("*").eq("conta_id", CONTA_ID).execute()
resp_cartoes = supabase.table("cartoes").select("*").eq("conta_id", CONTA_ID).execute()

df_gastos = pd.DataFrame(resp_gastos.data) if resp_gastos.data else pd.DataFrame()
df_rendas = pd.DataFrame(resp_rendas.data) if resp_rendas.data else pd.DataFrame()

# INICIALIZA CATEGORIAS PADRÃO SE VAZIO
if not resp_categorias.data:
    padroes_cat = ["Alimentação/Mercado", "Apartamento", "Carro", "Casa/Doméstico", "Compras Gerais", "Compras Online", "Entretenimento", "Farmácia", "Lazer", "Serviços", "Transporte"]
    for p in padroes_cat:
        supabase.table("categorias").insert({"conta_id": CONTA_ID, "nome": p}).execute()
    resp_categorias = supabase.table("categorias").select("*").eq("conta_id", CONTA_ID).execute()

df_categorias = pd.DataFrame(resp_categorias.data)
categorias_banco = df_categorias['nome'].tolist() if not df_categorias.empty else ["Compras Gerais"]

# INICIALIZA CARTÕES PADRÃO SE VAZIO
if not resp_cartoes.data:
    padroes_cart = ["Santander", "Itaú", "Bradesco", "Nubank"]
    for c in padroes_cart:
        supabase.table("cartoes").insert({"conta_id": CONTA_ID, "nome": c}).execute()
    resp_cartoes = supabase.table("cartoes").select("*").eq("conta_id", CONTA_ID).execute()

df_cartoes = pd.DataFrame(resp_cartoes.data)
cartoes_banco = ["Nenhum"] + (df_cartoes['nome'].tolist() if not df_cartoes.empty else [])

# SANITIZAÇÃO DE DADOS (Garante que nenhuma categoria ou campo fique NULO)
if not df_gastos.empty:
    df_gastos['categoria'] = df_gastos['categoria'].fillna("Compras Gerais").replace("", "Compras Gerais")
    df_gastos['comprador'] = df_gastos['comprador'].fillna(NOME_USUARIO_1)
    df_gastos['forma_pagamento'] = df_gastos['forma_pagamento'].fillna("Cartão de Crédito")
    df_gastos['cartao'] = df_gastos['cartao'].fillna("Nenhum")
    df_gastos['status_pagamento'] = df_gastos['status_pagamento'].fillna("Pendente")
    
    # Adiciona à lista de categorias qualquer uma que exista nos lançamentos mas não na tabela de categorias
    for c_exist in df_gastos['categoria'].unique():
        if c_exist not in categorias_banco:
            categorias_banco.append(c_exist)

    df_gastos['data_compra'] = pd.to_datetime(df_gastos['data_compra'])
    df_gastos['mes_ano'] = df_gastos['data_compra'].dt.strftime('%Y-%m')

if not df_rendas.empty:
    df_rendas['mes_referencia'] = pd.to_datetime(df_rendas['mes_referencia'])
    df_rendas['mes_ano'] = df_rendas['mes_referencia'].dt.strftime('%Y-%m')

# ------------------------------------------
# ABA 1: DASHBOARD (Filtros Avançados e Totais)
# ------------------------------------------
with aba_dashboard:
    st.subheader("🔍 Filtros de Visualização")
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    
    visao = col_f1.selectbox("De quem é a visão?", ["Visão Geral (Casal)", NOME_USUARIO_1, NOME_USUARIO_2] if MODO_CASAL else [NOME_USUARIO_1])
    
    if not df_gastos.empty:
        meses_disp = sorted(df_gastos['mes_ano'].unique().tolist(), reverse=True)
        filtro_mes = col_f2.selectbox("Mês de Referência", ["Todos"] + meses_disp)
        
        filtro_cat = col_f3.selectbox("Filtrar por Categoria", ["Todas"] + categorias_banco)
        filtro_forma = col_f4.selectbox("Forma de Pagamento / Cartão", ["Todos"] + ["Pix", "Débito", "Boleto", "Cartão de Crédito"] + [f"Cartão {c}" for c in cartoes_banco if c != "Nenhum"])

        col_f5, col_f6 = st.columns(2)
        filtro_status = col_f5.selectbox("Status do Pagamento", ["Todos", "Pago", "Pendente"])
        usar_dia = col_f6.checkbox("Filtrar por um dia específico?")
        filtro_dia = col_f6.date_input("Escolha o dia") if usar_dia else None
        
        # APLICAÇÃO DOS FILTROS
        df_filtrado = df_gastos.copy()
        
        if filtro_mes != "Todos": df_filtrado = df_filtrado[df_filtrado['mes_ano'] == filtro_mes]
        if usar_dia and filtro_dia: df_filtrado = df_filtrado[df_filtrado['data_compra'].dt.date == filtro_dia]
        if filtro_cat != "Todas": df_filtrado = df_filtrado[df_filtrado['categoria'] == filtro_cat]
        if filtro_status != "Todos": df_filtrado = df_filtrado[df_filtrado['status_pagamento'] == filtro_status]
        
        if filtro_forma != "Todos":
            if filtro_forma.startswith("Cartão "):
                nome_c = filtro_forma.replace("Cartão ", "")
                df_filtrado = df_filtrado[(df_filtrado['forma_pagamento'] == "Cartão de Crédito") & (df_filtrado['cartao'] == nome_c)]
            else:
                df_filtrado = df_filtrado[df_filtrado['forma_pagamento'] == filtro_forma]
            
        if visao != "Visão Geral (Casal)":
            df_indiv = df_filtrado[df_filtrado['comprador'] == visao].copy()
            df_juntos = df_filtrado[df_filtrado['comprador'] == "Juntos (Dividido 50/50)"].copy()
            df_juntos['valor'] = df_juntos['valor'] / 2 
            df_filtrado = pd.concat([df_indiv, df_juntos])

        total_gasto = df_filtrado['valor'].sum()
        
        st.divider()
        st.subheader("Resumo do Período Filtrado")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Gasto (da visão)", formatar_moeda(total_gasto))
        
        if not df_rendas.empty:
            df_rendas_filtro = df_rendas.copy()
            if filtro_mes != "Todos": df_rendas_filtro = df_rendas_filtro[df_rendas_filtro['mes_ano'] == filtro_mes]
            if visao == "Visão Geral (Casal)": total_renda = df_rendas_filtro['valor'].sum()
            else: total_renda = df_rendas_filtro[df_rendas_filtro['usuario'] == visao]['valor'].sum()
            
            saldo = total_renda - total_gasto
            delta_str = formatar_moeda(saldo).replace("R$ ", "")
            if saldo < 0: delta_str = "-" + delta_str.replace("-", "")
            
            c2.metric("Renda Total do Período", formatar_moeda(total_renda))
            c3.metric("Saldo Sobrando", formatar_moeda(saldo), delta=delta_str)
        st.divider()

        col_graf1, col_graf2 = st.columns(2)
        with col_graf1:
            st.write("### 📈 Gastos no Período")
            if not df_filtrado.empty:
                graf_tempo = df_filtrado.groupby('data_compra', as_index=False)['valor'].sum()
                st.bar_chart(graf_tempo, x="data_compra", y="valor")
        with col_graf2:
            st.write("### 🍕 Gastos por Categoria")
            if not df_filtrado.empty:
                graf_cat = df_filtrado.groupby('categoria', as_index=False)['valor'].sum()
                st.bar_chart(graf_cat, x="categoria", y="valor")

        # TABELA DE HISTÓRICO COM RESUMO DE SOMA TOTAL
        st.write("### ✏️ Histórico de Lançamentos")
        st.info(f"💡 **Total dos Lançamentos Exibidos na Tabela Abaixo:** **{formatar_moeda(total_gasto)}**")
        st.caption("*(Para ordenar, clique no título de qualquer coluna. Para excluir, marque a linha e aperte 'Delete')*")
        
        df_exibicao = df_filtrado[['id', 'data_compra', 'descricao', 'valor', 'valor_total', 'categoria', 'comprador', 'forma_pagamento', 'cartao', 'status_pagamento', 'parcela_atual', 'total_parcelas']].copy()
        df_exibicao['data_compra'] = df_exibicao['data_compra'].dt.date
        df_exibicao['valor'] = df_exibicao['valor'].apply(apenas_numero_br)
        df_exibicao['valor_total'] = df_exibicao['valor_total'].apply(apenas_numero_br)
        
        editado = st.data_editor(
            df_exibicao, key="editor_gastos", use_container_width=True, num_rows="dynamic",
            column_config={
                "id": None, 
                "data_compra": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "descricao": st.column_config.TextColumn("Descrição"),
                "valor": st.column_config.TextColumn("Valor Parcela (R$)"), 
                "valor_total": st.column_config.TextColumn("Total Compra (R$)"),
                "categoria": st.column_config.SelectboxColumn("Categoria", options=categorias_banco, required=True),
                "comprador": st.column_config.SelectboxColumn("De quem é?", options=OPCOES_COMPRADOR, required=True),
                "forma_pagamento": st.column_config.SelectboxColumn("Pagamento", options=["Cartão de Crédito", "Pix", "Débito", "Boleto"], required=True),
                "cartao": st.column_config.SelectboxColumn("Cartão", options=cartoes_banco, required=True),
                "status_pagamento": st.column_config.SelectboxColumn("Status", options=["Pago", "Pendente"], required=True),
                "parcela_atual": st.column_config.NumberColumn("Parcela Nº", min_value=1),
                "total_parcelas": st.column_config.NumberColumn("Total", min_value=1)
            }, hide_index=True
        )

        if st.button("Salvar Alterações/Exclusões"):
            alteracoes = st.session_state.editor_gastos
            fez_algo = False
            if alteracoes.get("deleted_rows"):
                for row_idx in alteracoes["deleted_rows"]:
                    id_apagar = df_exibicao.iloc[row_idx]['id']
                    supabase.table("gastos").delete().eq("id", int(id_apagar)).execute()
                fez_algo = True
            if alteracoes.get("edited_rows"):
                for row_idx, mudancas in alteracoes["edited_rows"].items():
                    id_editar = df_exibicao.iloc[row_idx]['id']
                    if 'data_compra' in mudancas: mudancas['data_compra'] = mudancas['data_compra'] + "T00:00:00"
                    if 'valor' in mudancas: mudancas['valor'] = texto_para_float(mudancas['valor'])
                    if 'valor_total' in mudancas: mudancas['valor_total'] = texto_para_float(mudancas['valor_total'])
                    supabase.table("gastos").update(mudancas).eq("id", int(id_editar)).execute()
                fez_algo = True
            if fez_algo:
                st.success("Banco de dados atualizado com sucesso! Recarregando...")
                st.rerun()
    else:
        st.info("Nenhum gasto registrado ainda.")

# ------------------------------------------
# ABA 2: ADICIONAR GASTO MANUAL
# ------------------------------------------
with aba_add_manual:
    st.subheader("Registrar Nova Compra")
    
    desc = st.text_input("O que foi comprado? *", key="g_desc")
    data_compra = st.date_input("Data da Compra *", value=date.today())
    comprador = st.radio("De quem é essa conta? *", OPCOES_COMPRADOR)
    cat_selecionada = st.selectbox("Categoria *", categorias_banco)
    
    col_pag1, col_pag2 = st.columns(2)
    forma_pag = col_pag1.selectbox("Forma de Pagamento *", ["Cartão de Crédito", "Pix", "Débito", "Boleto"])
    
    cartao_selecionado = "Nenhum"
    status_inicial = "Pago"
    
    if forma_pag == "Cartão de Crédito":
        cartao_selecionado = col_pag2.selectbox("Qual Cartão de Crédito?", [c for c in cartoes_banco if c != "Nenhum"])
        status_inicial = col_pag2.radio("Status do Pagamento:", ["Pendente (Vence dia 1º)", "Pago"], index=0)
    
    tipo_pagamento = st.radio("Modalidade:", ["À vista", "Parcelada"])
    
    if tipo_pagamento == "À vista":
        val_vista_txt = st.text_input("Valor da Compra (R$) *", value="0,00", key="g_val_vista")
        valor_total_compra = texto_para_float(val_vista_txt)
        valor_parcela = valor_total_compra
        total_parcelas = 1
        parcela_atual = 1
    else:
        col_vt, col_vp = st.columns(2)
        val_tot_txt = col_vt.text_input("Valor TOTAL da Compra (R$) *", value="0,00", key="g_val_parc_tot")
        valor_total_compra = texto_para_float(val_tot_txt)
        val_parc_txt = col_vp.text_input("Valor da PARCELA Mensal (R$) *", value="0,00", key="g_val_parc_mensal")
        valor_parcela = texto_para_float(val_parc_txt)
        
        col_p1, col_p2 = st.columns(2)
        total_parcelas = col_p2.number_input("Quantidade Total de Parcelas *", min_value=2, value=2)
        parcela_atual = col_p1.number_input("Qual parcela é essa? *", min_value=1, value=1)
        st.info(f"O valor de cada parcela será: **{formatar_moeda(valor_parcela)}**")
        
    recorrente = st.checkbox("Compra recorrente mensal (Fixo)?")
    
    if st.button("Salvar Gasto", type="primary"):
        if not desc.strip() or valor_total_compra <= 0:
            st.error("Erro: Preencha a descrição e o valor!")
        else:
            novo_gasto = {
                "conta_id": CONTA_ID, "descricao": desc,
                "valor": float(valor_parcela), "valor_total": float(valor_total_compra),
                "categoria": cat_selecionada, "comprador": comprador,
                "data_compra": data_compra.isoformat(), "recorrente": recorrente,
                "parcela_atual": int(parcela_atual), "total_parcelas": int(total_parcelas),
                "forma_pagamento": forma_pag, "cartao": cartao_selecionado,
                "status_pagamento": "Pago" if forma_pag != "Cartão de Crédito" else status_inicial
            }
            supabase.table("gastos").insert(novo_gasto).execute()
            
            for key in ['g_desc', 'g_val_vista', 'g_val_parc_tot', 'g_val_parc_mensal']:
                if key in st.session_state: del st.session_state[key]
            st.success("Gasto salvo com sucesso!")
            st.rerun()

# ------------------------------------------
# ABA 3: RENDAS E SALÁRIOS
# ------------------------------------------
with aba_renda:
    st.subheader("💰 Salários e Sobras")
    with st.form("form_renda", clear_on_submit=True):
        usuario_renda = st.selectbox("Quem recebeu?", OPCOES_COMPRADOR[:2])
        mes_renda = st.date_input("Data do Recebimento", value=date.today())
        valor_renda_txt = st.text_input("Valor Recebido (R$)", value="0,00")
        valor_renda = texto_para_float(valor_renda_txt)
        
        if st.form_submit_button("Salvar Salário") and valor_renda > 0:
            supabase.table("receitas").insert({
                "conta_id": CONTA_ID, "usuario": usuario_renda,
                "mes_referencia": mes_renda.isoformat(), "valor": float(valor_renda)
            }).execute()
            st.success("Salário cadastrado!")
            st.rerun()
            
    st.divider()
    if not df_rendas.empty:
        st.write("### ✏️ Edição de Salários")
        df_r_exib = df_rendas[['id', 'mes_referencia', 'usuario', 'valor']].copy()
        df_r_exib['mes_referencia'] = df_r_exib['mes_referencia'].dt.date
        df_r_exib['valor'] = df_r_exib['valor'].apply(apenas_numero_br)
        
        edit_renda = st.data_editor(
            df_r_exib, key="editor_rendas", num_rows="dynamic", use_container_width=True,
            column_config={
                "id": None, 
                "mes_referencia": st.column_config.DateColumn("Data", format="DD/MM/YYYY"), 
                "usuario": st.column_config.SelectboxColumn("Pessoa", options=OPCOES_COMPRADOR[:2], required=True), 
                "valor": st.column_config.TextColumn("Valor (R$)") 
            }, hide_index=True
        )
        if st.button("Salvar Alterações de Salário"):
            alt_r = st.session_state.editor_rendas
            fez_algo_r = False
            if alt_r.get("deleted_rows"):
                for idx in alt_r["deleted_rows"]:
                    id_del = df_r_exib.iloc[idx]['id']
                    supabase.table("receitas").delete().eq("id", int(id_del)).execute()
                fez_algo_r = True
            if alt_r.get("edited_rows"):
                for idx, mudancas in alt_r["edited_rows"].items():
                    id_upd = df_r_exib.iloc[idx]['id']
                    if 'mes_referencia' in mudancas: mudancas['mes_referencia'] = mudancas['mes_referencia'] + "T00:00:00"
                    if 'valor' in mudancas: mudancas['valor'] = texto_para_float(mudancas['valor'])
                    supabase.table("receitas").update(mudancas).eq("id", int(id_upd)).execute()
                fez_algo_r = True
            if fez_algo_r:
                st.success("Salários atualizados!")
                st.rerun()

# ------------------------------------------
# ABA 4: IMPORTAR FATURA (Com Seleção de Cartão)
# ------------------------------------------
with aba_pdf:
    if 'fatura_em_revisao' not in st.session_state:
        st.subheader("Importar Fatura de Cartão")
        col_pdf1, col_pdf2 = st.columns(2)
        dono_fatura = col_pdf1.radio("Essa fatura é de quem?", OPCOES_COMPRADOR, key="dono_fat")
        cartao_fatura = col_pdf2.selectbox("Qual Cartão de Crédito é este?", [c for c in cartoes_banco if c != "Nenhum"])
        data_fatura = col_pdf2.date_input("Data base dessa fatura", value=date.today())
        
        arquivo_pdf = st.file_uploader("Escolha o arquivo PDF", type=["pdf"])
        
        if arquivo_pdf is not None and st.button("Analisar Fatura"):
            with st.spinner("A IA está analisando a fatura e categorizando tudo..."):
                try:
                    pdf_bytes = arquivo_pdf.getvalue()
                    prompt = f"""
                    Leia a fatura de cartão anexada. Extraia APENAS as compras realizadas.
                    Ignore pagamentos de fatura, estornos, saldos anteriores ou encargos.
                    Retorne EXCLUSIVAMENTE um array JSON. Cada objeto deve conter:
                    - "data_compra": (string, formato YYYY-MM-DD)
                    - "descricao": (string, nome do estabelecimento)
                    - "valor": (numero decimal, parcela do mês)
                    - "valor_total": (numero decimal, total da compra)
                    - "categoria": (string, tente usar uma destas se fizer sentido: {', '.join(categorias_banco)})
                    - "parcela_atual": (inteiro)
                    - "total_parcelas": (inteiro)
                    """
                    modelos_para_testar = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash-latest', 'gemini-1.5-flash']
                    resposta_ia = None
                    ultimo_erro = None
                    for nome_modelo in modelos_para_testar:
                        try:
                            mod = genai.GenerativeModel(nome_modelo)
                            resposta_ia = mod.generate_content([prompt, {"mime_type": "application/pdf", "data": pdf_bytes}])
                            if resposta_ia and resposta_ia.text: break
                        except Exception as err:
                            ultimo_erro = err
                            continue
                            
                    if not resposta_ia or not resposta_ia.text:
                        raise ultimo_erro if ultimo_erro else Exception("Nenhum modelo respondeu.")

                    texto_json = resposta_ia.text.strip().removeprefix('```json').removesuffix('```').strip()
                    compras_extraidas = json.loads(texto_json)
                    
                    for c in compras_extraidas:
                        c['comprador'] = dono_fatura
                        c['cartao'] = cartao_fatura
                        c['forma_pagamento'] = "Cartão de Crédito"
                        c['status_pagamento'] = "Pendente"
                        if not c.get("categoria"): c["categoria"] = "Compras Gerais"
                        if not c.get("data_compra"): c["data_compra"] = data_fatura.isoformat()
                    
                    st.session_state['fatura_em_revisao'] = compras_extraidas
                    st.session_state['fatura_data_base'] = data_fatura
                    st.rerun()
                except Exception as e:
                    st.error("Erro na leitura. Certifique-se de que é um PDF válido.")
                    st.error(f"Erro técnico: {e}")
                    
        st.divider()
        st.subheader("🗑️ Desfazer Importações Recentes")
        if not df_gastos.empty and 'lote_importacao' in df_gastos.columns:
            df_com_lote = df_gastos[df_gastos['lote_importacao'].notna()]
            if not df_com_lote.empty:
                lotes_validos = df_com_lote['lote_importacao'].unique()
                lote_selecionado = st.selectbox("Selecione o Lote da Fatura que quer apagar", lotes_validos)
                qtd_lote = len(df_com_lote[df_com_lote['lote_importacao'] == lote_selecionado])
                st.write(f"Essa importação contém **{qtd_lote} lançamentos**.")
                
                if st.button("🚨 Excluir esta Fatura Inteira", type="primary"):
                    supabase.table("gastos").delete().eq("conta_id", CONTA_ID).eq("lote_importacao", lote_selecionado).execute()
                    st.success("Fatura desfeita com sucesso!")
                    st.rerun()
                    
    else:
        st.subheader("🔍 Validação da Fatura")
        st.write("Dê dois cliques nas células para alterar informações, ajustar valores ou apagar linhas.")
        
        df_rev = pd.DataFrame(st.session_state['fatura_em_revisao'])
        
        col_nec = ['data_compra', 'descricao', 'valor', 'valor_total', 'categoria', 'comprador', 'cartao', 'parcela_atual', 'total_parcelas']
        for col in col_nec:
            if col not in df_rev.columns:
                if 'parcela' in col: df_rev[col] = 1
                elif 'valor' in col: df_rev[col] = 0.0
                elif col == 'comprador': df_rev[col] = OPCOES_COMPRADOR[0]
                elif col == 'categoria': df_rev[col] = "Compras Gerais"
                elif col == 'cartao': df_rev[col] = cartoes_banco[1] if len(cartoes_banco) > 1 else "Nenhum"
                elif col == 'data_compra': df_rev[col] = st.session_state['fatura_data_base']
                else: df_rev[col] = ""
                
        df_rev['data_compra'] = pd.to_datetime(df_rev['data_compra'], errors='coerce').dt.date
        df_rev['data_compra'] = df_rev['data_compra'].fillna(st.session_state['fatura_data_base'])
        
        df_rev['valor'] = df_rev['valor'].apply(apenas_numero_br)
        df_rev['valor_total'] = df_rev['valor_total'].apply(apenas_numero_br)
        
        opcoes_cat_fatura = categorias_banco.copy()
        for cat in df_rev['categoria'].dropna().unique():
            if cat not in opcoes_cat_fatura and cat != "": opcoes_cat_fatura.append(cat)
                
        fatura_editada = st.data_editor(
            df_rev, key="editor_fatura", use_container_width=True, num_rows="dynamic",
            column_config={
                "data_compra": st.column_config.DateColumn("Data da Compra", format="DD/MM/YYYY"),
                "descricao": st.column_config.TextColumn("Descrição da Compra"),
                "valor": st.column_config.TextColumn("Valor PARCELA (R$)"),
                "valor_total": st.column_config.TextColumn("Valor TOTAL (R$)"),
                "categoria": st.column_config.SelectboxColumn("Categoria", options=opcoes_cat_fatura, required=True),
                "comprador": st.column_config.SelectboxColumn("De quem é?", options=OPCOES_COMPRADOR, required=True),
                "cartao": st.column_config.SelectboxColumn("Cartão", options=[c for c in cartoes_banco if c != "Nenhum"], required=True),
                "parcela_atual": st.column_config.NumberColumn("Parcela Nº", min_value=1),
                "total_parcelas": st.column_config.NumberColumn("Total Parcelas", min_value=1),
            }, hide_index=True
        )
        
        st.divider()
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        
        if col_btn1.button("✅ Confirmar e Salvar Fatura", type="primary"):
            compras_finais = fatura_editada.to_dict('records')
            lote_id = f"Fatura_{datetime.now().strftime('%d-%m-%Y_%H:%M:%S')}"
            
            for c in compras_finais:
                data_final = c["data_compra"].isoformat() if hasattr(c["data_compra"], 'isoformat') else str(c["data_compra"])
                valor_p = texto_para_float(c["valor"])
                valor_t = texto_para_float(c.get("valor_total", c["valor"]))
                cat_f = c["categoria"] if c["categoria"] else "Compras Gerais"
                
                supabase.table("gastos").insert({
                    "conta_id": CONTA_ID, "descricao": c["descricao"],
                    "valor": float(valor_p), "valor_total": float(valor_t), 
                    "categoria": cat_f, "comprador": c["comprador"],
                    "data_compra": data_final, "recorrente": False,
                    "parcela_atual": int(c.get("parcela_atual", 1)), "total_parcelas": int(c.get("total_parcelas", 1)),
                    "forma_pagamento": "Cartão de Crédito", "cartao": c["cartao"],
                    "status_pagamento": "Pendente", "lote_importacao": lote_id
                }).execute()
            
            del st.session_state['fatura_em_revisao']
            del st.session_state['fatura_data_base']
            st.success("Fatura salva com sucesso!")
            st.rerun()
            
        if col_btn2.button("🪄 Padronizar repetições"):
            alt_f = st.session_state.editor_fatura
            fatura_atual = st.session_state['fatura_em_revisao']
            
            mapa_edicoes = {}
            if alt_f.get("edited_rows"):
                for idx_str, mudancas in alt_f["edited_rows"].items():
                    if "categoria" in mudancas or "comprador" in mudancas:
                        desc = fatura_atual[int(idx_str)]["descricao"]
                        mapa_edicoes[desc] = mudancas
                        
            if mapa_edicoes:
                mudou_algo = False
                for i, item in enumerate(fatura_atual):
                    if str(i) in alt_f.get("edited_rows", {}): item.update(alt_f["edited_rows"][str(i)])
                    desc = item.get("descricao", "")
                    if desc in mapa_edicoes:
                        if "categoria" in mapa_edicoes[desc] and item.get("categoria") != mapa_edicoes[desc]["categoria"]:
                            item["categoria"] = mapa_edicoes[desc]["categoria"]
                            mudou_algo = True
                        if "comprador" in mapa_edicoes[desc] and item.get("comprador") != mapa_edicoes[desc]["comprador"]:
                            item["comprador"] = mapa_edicoes[desc]["comprador"]
                            mudou_algo = True
                            
                if mudou_algo:
                    st.session_state['fatura_em_revisao'] = fatura_atual
                    del st.session_state["editor_fatura"]
                    st.rerun()
            else:
                st.warning("Altere a Categoria ou o Comprador de pelo menos um item primeiro!")

        if col_btn3.button("❌ Cancelar Importação"):
            del st.session_state['fatura_em_revisao']
            del st.session_state['fatura_data_base']
            st.rerun()

# ------------------------------------------
# ABA 5: CATEGORIAS E CARTÕES
# ------------------------------------------
with aba_config:
    col_cfg1, col_cfg2 = st.columns(2)
    
    # SEÇÃO DE CATEGORIAS
    with col_cfg1:
        st.subheader("⚙️ Suas Categorias")
        with st.form("form_nova_cat", clear_on_submit=True):
            nova_cat = st.text_input("Criar Nova Categoria:")
            if st.form_submit_button("Salvar Categoria") and nova_cat.strip():
                if nova_cat.strip() not in categorias_banco:
                    supabase.table("categorias").insert({"conta_id": CONTA_ID, "nome": nova_cat.strip()}).execute()
                    st.success("Categoria cadastrada!")
                    st.rerun()

        if not df_categorias.empty:
            df_cat_exib = df_categorias[['id', 'nome']].copy()
            edit_cat = st.data_editor(
                df_cat_exib, key="editor_categorias", num_rows="dynamic", use_container_width=True,
                column_config={"id": None, "nome": st.column_config.TextColumn("Nome da Categoria", required=True)}, hide_index=True
            )
            if st.button("Salvar Alterações de Categorias"):
                alt_c = st.session_state.editor_categorias
                fez_algo = False
                if alt_c.get("deleted_rows"):
                    for idx in alt_c["deleted_rows"]:
                        id_del = df_cat_exib.iloc[idx]['id']
                        supabase.table("categorias").delete().eq("id", int(id_del)).execute()
                    fez_algo = True
                if alt_c.get("edited_rows"):
                    for idx, mudancas in alt_c["edited_rows"].items():
                        id_upd = df_cat_exib.iloc[idx]['id']
                        supabase.table("categorias").update(mudancas).eq("id", int(id_upd)).execute()
                    fez_algo = True
                if fez_algo: st.rerun()

    # SEÇÃO DE CARTÕES DE CRÉDITO
    with col_cfg2:
        st.subheader("💳 Seus Cartões de Crédito")
        with st.form("form_novo_cartao", clear_on_submit=True):
            novo_cartao = st.text_input("Cadastrar Novo Cartão (Ex: Santander, Itaú, Bradesco):")
            if st.form_submit_button("Salvar Cartão") and novo_cartao.strip():
                if novo_cartao.strip() not in cartoes_banco:
                    supabase.table("cartoes").insert({"conta_id": CONTA_ID, "nome": novo_cartao.strip()}).execute()
                    st.success("Cartão cadastrado!")
                    st.rerun()

        if not df_cartoes.empty:
            df_cart_exib = df_cartoes[['id', 'nome']].copy()
            edit_cart = st.data_editor(
                df_cart_exib, key="editor_cartoes", num_rows="dynamic", use_container_width=True,
                column_config={"id": None, "nome": st.column_config.TextColumn("Nome do Cartão", required=True)}, hide_index=True
            )
            if st.button("Salvar Alterações de Cartões"):
                alt_crt = st.session_state.editor_cartoes
                fez_algo_crt = False
                if alt_crt.get("deleted_rows"):
                    for idx in alt_crt["deleted_rows"]:
                        id_del = df_cart_exib.iloc[idx]['id']
                        supabase.table("cartoes").delete().eq("id", int(id_del)).execute()
                    fez_algo_crt = True
                if alt_crt.get("edited_rows"):
                    for idx, mudancas in alt_crt["edited_rows"].items():
                        id_upd = df_cart_exib.iloc[idx]['id']
                        supabase.table("cartoes").update(mudancas).eq("id", int(id_upd)).execute()
                    fez_algo_crt = True
                if fez_algo_crt: st.rerun()

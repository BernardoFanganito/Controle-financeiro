import streamlit as st
import google.generativeai as genai
from supabase import create_client
import PyPDF2
import json
import pandas as pd
from datetime import datetime, date

# ==========================================
# CONFIGURAÇÕES INICIAIS
# ==========================================
st.set_page_config(page_title="Controle Financeiro", page_icon="💸", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)
modelo_ia = genai.GenerativeModel('gemini-1.5-flash')

# ==========================================
# SISTEMA DE LOGIN (COM MEMÓRIA / PERSISTÊNCIA)
# ==========================================
# Tenta recuperar o login da URL caso a página seja atualizada
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
                # Salva o ID na URL para não deslogar no F5
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
        
        nome_2 = ""
        if tipo_conta == "Em Casal":
            nome_2 = st.text_input("Nome do Parceiro(a) (Pessoa 2)")
        
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
        st.query_params.clear() # Limpa a URL
        st.session_state.clear() # Limpa a memória
        st.rerun()

st.title("💸 Controle Financeiro")
aba_dashboard, aba_add_manual, aba_renda, aba_pdf = st.tabs([
    "📊 Visão e Edição", "✍️ Registrar Compra", "💰 Meus Salários", "📄 Importar Fatura"
])

# Busca dados
resp_gastos = supabase.table("gastos").select("*").eq("conta_id", CONTA_ID).execute()
resp_rendas = supabase.table("receitas").select("*").eq("conta_id", CONTA_ID).execute()
df_gastos = pd.DataFrame(resp_gastos.data) if resp_gastos.data else pd.DataFrame()
df_rendas = pd.DataFrame(resp_rendas.data) if resp_rendas.data else pd.DataFrame()

if not df_gastos.empty:
    df_gastos['data_compra'] = pd.to_datetime(df_gastos['data_compra'])
    df_gastos['mes_ano'] = df_gastos['data_compra'].dt.strftime('%Y-%m')
if not df_rendas.empty:
    df_rendas['mes_referencia'] = pd.to_datetime(df_rendas['mes_referencia'])
    df_rendas['mes_ano'] = df_rendas['mes_referencia'].dt.strftime('%Y-%m')

# ------------------------------------------
# ABA 1: DASHBOARD (Filtros e Exclusão)
# ------------------------------------------
with aba_dashboard:
    col_v1, col_v2, col_v3 = st.columns(3)
    visao = col_v1.selectbox("De quem é a visão?", ["Visão Geral (Casal)", NOME_USUARIO_1, NOME_USUARIO_2] if MODO_CASAL else [NOME_USUARIO_1])
    
    if not df_gastos.empty:
        meses_disp = sorted(df_gastos['mes_ano'].unique().tolist(), reverse=True)
        filtro_mes = col_v2.selectbox("Filtrar por Mês", ["Todos"] + meses_disp)
        
        usar_dia = col_v3.checkbox("Filtrar por um dia específico?")
        if usar_dia:
            filtro_dia = col_v3.date_input("Escolha o dia")
        
        df_filtrado = df_gastos.copy()
        if filtro_mes != "Todos":
            df_filtrado = df_filtrado[df_filtrado['mes_ano'] == filtro_mes]
        if usar_dia:
            df_filtrado = df_filtrado[df_filtrado['data_compra'].dt.date == filtro_dia]
            
        if visao != "Visão Geral (Casal)":
            df_indiv = df_filtrado[df_filtrado['comprador'] == visao].copy()
            df_juntos = df_filtrado[df_filtrado['comprador'] == "Juntos (Dividido 50/50)"].copy()
            df_juntos['valor'] = df_juntos['valor'] / 2 
            df_filtrado = pd.concat([df_indiv, df_juntos])

        total_gasto = df_filtrado['valor'].sum()
        
        st.subheader("Resumo do Período Filtrado")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Gasto (da visão)", f"R$ {total_gasto:.2f}")
        
        if not df_rendas.empty:
            df_rendas_filtro = df_rendas.copy()
            if filtro_mes != "Todos":
                df_rendas_filtro = df_rendas_filtro[df_rendas_filtro['mes_ano'] == filtro_mes]
                
            if visao == "Visão Geral (Casal)":
                total_renda = df_rendas_filtro['valor'].sum()
            else:
                total_renda = df_rendas_filtro[df_rendas_filtro['usuario'] == visao]['valor'].sum()
            
            c2.metric("Renda Total do Período", f"R$ {total_renda:.2f}")
            c3.metric("Saldo Sobrando", f"R$ {(total_renda - total_gasto):.2f}", delta=float(total_renda - total_gasto))
        
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

        st.write("### ✏️ Histórico (Edite, ou Selecione a linha e aperte 'Delete' para excluir)")
        
        df_exibicao = df_filtrado[['id', 'data_compra', 'descricao', 'valor', 'valor_total', 'categoria', 'comprador', 'parcela_atual', 'total_parcelas']].copy()
        df_exibicao['data_compra'] = df_exibicao['data_compra'].dt.date
        
        editado = st.data_editor(
            df_exibicao, key="editor_gastos", use_container_width=True, num_rows="dynamic",
            column_config={
                "id": None, "data_compra": st.column_config.DateColumn("Data"),
                "descricao": st.column_config.TextColumn("Descrição"),
                "valor": st.column_config.NumberColumn("Valor Parcela (R$)", format="%.2f"),
                "valor_total": st.column_config.NumberColumn("Total Compra (R$)", format="%.2f"),
                "categoria": st.column_config.TextColumn("Categoria"),
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
                    supabase.table("gastos").update(mudancas).eq("id", int(id_editar)).execute()
                fez_algo = True
                
            if fez_algo:
                st.success("Banco de dados atualizado com sucesso! Recarregando...")
                st.rerun()
    else:
        st.info("Nenhum gasto registrado ainda.")

# ------------------------------------------
# ABA 2: ADICIONAR GASTO MANUAL (Dinamismo sem st.form)
# ------------------------------------------
with aba_add_manual:
    st.subheader("Registrar Nova Compra")
    
    # Criando as opções de categoria dinâmicas lendo do banco
    categorias_banco = ["Comida/Mercado", "Compras Gerais", "Aluguel", "Casa/Doméstico", "Viagem", "Lazer/Saídas"]
    if not df_gastos.empty:
        cats_usadas = df_gastos['categoria'].dropna().unique().tolist()
        for c in cats_usadas:
            if c not in categorias_banco:
                categorias_banco.append(c)
                
    categorias_banco.append("+ Criar Nova Categoria") # Opção extra no final

    # Inputs Livres (Reagem na hora)
    desc = st.text_input("O que foi comprado? *", key="g_desc")
    data_compra = st.date_input("Data da Compra *", value=date.today())
    comprador = st.radio("De quem é essa conta? *", OPCOES_COMPRADOR)
    
    cat_selecionada = st.selectbox("Categoria *", categorias_banco)
    if cat_selecionada == "+ Criar Nova Categoria":
        categoria_final = st.text_input("Digite o nome da sua nova Categoria *", key="g_cat_nova")
    else:
        categoria_final = cat_selecionada
    
    tipo_pagamento = st.radio("Forma de Pagamento:", ["À vista", "Parcelada"])
    
    if tipo_pagamento == "À vista":
        valor_total_compra = st.number_input("Valor da Compra (R$) *", min_value=0.00, step=10.00, format="%.2f", key="g_val_vista")
        valor_parcela = valor_total_compra
        total_parcelas = 1
        parcela_atual = 1
    else:
        valor_total_compra = st.number_input("Valor Total da Compra (R$) *", min_value=0.00, step=10.00, format="%.2f", key="g_val_parc")
        col_p1, col_p2 = st.columns(2)
        total_parcelas = col_p2.number_input("Quantidade Total de Parcelas *", min_value=2, value=2)
        parcela_atual = col_p1.number_input("Qual parcela é essa? *", min_value=1, value=1)
        valor_parcela = valor_total_compra / total_parcelas if total_parcelas > 0 else 0
        st.info(f"O valor de cada parcela será: **R$ {valor_parcela:.2f}** (Este é o valor que aparecerá no relatório mensal)")
        
    recorrente = st.checkbox("Compra recorrente mensal (Fixo)?")
    
    if st.button("Salvar Gasto", type="primary"):
        if not desc.strip() or valor_total_compra <= 0:
            st.error("Erro: Preencha a descrição e o valor!")
        elif cat_selecionada == "+ Criar Nova Categoria" and not categoria_final.strip():
            st.error("Erro: Você esqueceu de digitar o nome da nova categoria!")
        else:
            novo_gasto = {
                "conta_id": CONTA_ID, "descricao": desc,
                "valor": float(valor_parcela), "valor_total": float(valor_total_compra),
                "categoria": categoria_final, "comprador": comprador,
                "data_compra": data_compra.isoformat(), "recorrente": recorrente,
                "parcela_atual": int(parcela_atual), "total_parcelas": int(total_parcelas)
            }
            supabase.table("gastos").insert(novo_gasto).execute()
            
            # Limpa os campos da tela deletando eles da memória antes de atualizar
            for key in ['g_desc', 'g_val_vista', 'g_val_parc', 'g_cat_nova']:
                if key in st.session_state:
                    del st.session_state[key]
                    
            st.success("Gasto salvo com sucesso!")
            st.rerun()

# ------------------------------------------
# ABA 3: RENDAS, HISTÓRICO EDITÁVEL
# ------------------------------------------
with aba_renda:
    st.subheader("💰 Salários e Sobras")
    with st.form("form_renda", clear_on_submit=True):
        usuario_renda = st.selectbox("Quem recebeu?", OPCOES_COMPRADOR[:2])
        mes_renda = st.date_input("Data do Recebimento", value=date.today())
        valor_renda = st.number_input("Valor Recebido (R$)", min_value=0.00, step=100.00, format="%.2f")
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
        
        edit_renda = st.data_editor(
            df_r_exib, key="editor_rendas", num_rows="dynamic", use_container_width=True,
            column_config={
                "id": None, "mes_referencia": st.column_config.DateColumn("Data"),
                "usuario": st.column_config.TextColumn("Pessoa"),
                "valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f")
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
                    supabase.table("receitas").update(mudancas).eq("id", int(id_upd)).execute()
                fez_algo_r = True
                
            if fez_algo_r:
                st.success("Salários atualizados!")
                st.rerun()

# ------------------------------------------
# ABA 4: IMPORTAR FATURA (PDF)
# ------------------------------------------
with aba_pdf:
    st.subheader("Importar Fatura")
    dono_fatura = st.radio("Essa fatura é de quem?", OPCOES_COMPRADOR, key="dono_fat")
    data_fatura = st.date_input("Data base dessa fatura", value=date.today())
    arquivo_pdf = st.file_uploader("Escolha o arquivo PDF", type=["pdf"])
    
    if arquivo_pdf is not None and st.button("Analisar Fatura"):
        with st.spinner("Lendo sua fatura..."):
            leitor = PyPDF2.PdfReader(arquivo_pdf)
            texto_fatura = "".join([p.extract_text() for p in leitor.pages])
            prompt = f"""
            Leia a fatura de cartão. Extraia apenas as compras realizadas.
            Retorne APENAS um array JSON válido. Cada objeto deve ter:
            "descricao", "valor", "categoria", "parcela_atual", "total_parcelas".
            Fatura: {texto_fatura}
            """
            try:
                resposta_ia = modelo_ia.generate_content(prompt)
                texto_json = resposta_ia.text.strip().removeprefix('```json').removesuffix('```').strip()
                compras = json.loads(texto_json)
                for c in compras:
                    supabase.table("gastos").insert({
                        "conta_id": CONTA_ID, "descricao": c["descricao"],
                        "valor": c["valor"], 
                        "valor_total": c["valor"], 
                        "categoria": c["categoria"], "comprador": dono_fatura,
                        "data_compra": data_fatura.isoformat(), "recorrente": False,
                        "parcela_atual": c.get("parcela_atual", 1), "total_parcelas": c.get("total_parcelas", 1)
                    }).execute()
                st.success(f"{len(compras)} compras salvas!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao processar: {e}")

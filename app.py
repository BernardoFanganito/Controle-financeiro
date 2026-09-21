import streamlit as st
import google.generativeai as genai
from supabase import create_client
import json
import pandas as pd
from datetime import datetime, date

# ==========================================
# FUNÇÃO DE FORMATAÇÃO BRASILEIRA (R$ 1.255,50)
# ==========================================
def formatar_moeda(valor):
    if pd.isna(valor):
        return "R$ 0,00"
    # Formata com 2 casas decimais e separador de milhares americano
    valor_str = f"{valor:,.2f}"
    # Inverte os pontos e vírgulas para o padrão brasileiro
    valor_str = valor_str.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {valor_str}"

# ==========================================
# CONFIGURAÇÕES INICIAIS
# ==========================================
st.set_page_config(page_title="Controle Financeiro", page_icon="💸", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)

# ==========================================
# SISTEMA DE LOGIN (COM MEMÓRIA / PERSISTÊNCIA)
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
aba_dashboard, aba_add_manual, aba_renda, aba_pdf = st.tabs([
    "📊 Visão e Edição", "✍️ Registrar Compra", "💰 Meus Salários", "📄 Importar Fatura"
])

# Busca dados do Banco
resp_gastos = supabase.table("gastos").select("*").eq("conta_id", CONTA_ID).execute()
resp_rendas = supabase.table("receitas").select("*").eq("conta_id", CONTA_ID).execute()
df_gastos = pd.DataFrame(resp_gastos.data) if resp_gastos.data else pd.DataFrame()
df_rendas = pd.DataFrame(resp_rendas.data) if resp_rendas.data else pd.DataFrame()

# Cria a lista global de categorias puxando as já cadastradas
categorias_banco = ["Comida/Mercado", "Compras Gerais", "Aluguel", "Casa/Doméstico", "Viagem", "Lazer/Saídas"]
if not df_gastos.empty:
    df_gastos['data_compra'] = pd.to_datetime(df_gastos['data_compra'])
    df_gastos['mes_ano'] = df_gastos['data_compra'].dt.strftime('%Y-%m')
    cats_usadas = df_gastos['categoria'].dropna().unique().tolist()
    for c in cats_usadas:
        if c not in categorias_banco:
            categorias_banco.append(c)

if not df_rendas.empty:
    df_rendas['mes_referencia'] = pd.to_datetime(df_rendas['mes_referencia'])
    df_rendas['mes_ano'] = df_rendas['mes_referencia'].dt.strftime('%Y-%m')

# ------------------------------------------
# ABA 1: DASHBOARD
# ------------------------------------------
with aba_dashboard:
    col_v1, col_v2, col_v3 = st.columns(3)
    visao = col_v1.selectbox("De quem é a visão?", ["Visão Geral (Casal)", NOME_USUARIO_1, NOME_USUARIO_2] if MODO_CASAL else [NOME_USUARIO_1])
    
    if not df_gastos.empty:
        meses_disp = sorted(df_gastos['mes_ano'].unique().tolist(), reverse=True)
        filtro_mes = col_v2.selectbox("Filtrar por Mês", ["Todos"] + meses_disp)
        usar_dia = col_v3.checkbox("Filtrar por um dia específico?")
        if usar_dia: filtro_dia = col_v3.date_input("Escolha o dia")
        
        df_filtrado = df_gastos.copy()
        if filtro_mes != "Todos": df_filtrado = df_filtrado[df_filtrado['mes_ano'] == filtro_mes]
        if usar_dia: df_filtrado = df_filtrado[df_filtrado['data_compra'].dt.date == filtro_dia]
            
        if visao != "Visão Geral (Casal)":
            df_indiv = df_filtrado[df_filtrado['comprador'] == visao].copy()
            df_juntos = df_filtrado[df_filtrado['comprador'] == "Juntos (Dividido 50/50)"].copy()
            df_juntos['valor'] = df_juntos['valor'] / 2 
            df_filtrado = pd.concat([df_indiv, df_juntos])

        total_gasto = df_filtrado['valor'].sum()
        
        st.subheader("Resumo do Período Filtrado")
        c1, c2, c3 = st.columns(3)
        
        # APLICANDO A FORMATAÇÃO BRASILEIRA AQUI
        c1.metric("Total Gasto (da visão)", formatar_moeda(total_gasto))
        
        if not df_rendas.empty:
            df_rendas_filtro = df_rendas.copy()
            if filtro_mes != "Todos": df_rendas_filtro = df_rendas_filtro[df_rendas_filtro['mes_ano'] == filtro_mes]
            if visao == "Visão Geral (Casal)": total_renda = df_rendas_filtro['valor'].sum()
            else: total_renda = df_rendas_filtro[df_rendas_filtro['usuario'] == visao]['valor'].sum()
            
            saldo = total_renda - total_gasto
            # Para manter a cor verde (positivo) ou vermelha (negativo) na setinha
            delta_str = formatar_moeda(saldo).replace("R$ ", "")
            if saldo < 0: delta_str = "-" + delta_str.replace("-", "")
            
            # APLICANDO A FORMATAÇÃO BRASILEIRA AQUI
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

        st.write("### ✏️ Histórico (Dê 2 cliques para Editar, ou selecione a linha e aperte 'Delete')")
        
        df_exibicao = df_filtrado[['id', 'data_compra', 'descricao', 'valor', 'valor_total', 'categoria', 'comprador', 'parcela_atual', 'total_parcelas']].copy()
        df_exibicao['data_compra'] = df_exibicao['data_compra'].dt.date
        
        editado = st.data_editor(
            df_exibicao, key="editor_gastos", use_container_width=True, num_rows="dynamic",
            column_config={
                "id": None, 
                "data_compra": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "descricao": st.column_config.TextColumn("Descrição"),
                "valor": st.column_config.NumberColumn("Valor Parcela (R$)", format="%.2f"),
                "valor_total": st.column_config.NumberColumn("Total Compra (R$)", format="%.2f"),
                "categoria": st.column_config.SelectboxColumn("Categoria", options=categorias_banco, required=True),
                "comprador": st.column_config.SelectboxColumn("De quem é?", options=OPCOES_COMPRADOR, required=True),
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
    
    opcoes_cat_manual = categorias_banco.copy()
    opcoes_cat_manual.append("+ Criar Nova Categoria")

    desc = st.text_input("O que foi comprado? *", key="g_desc")
    data_compra = st.date_input("Data da Compra *", value=date.today())
    comprador = st.radio("De quem é essa conta? *", OPCOES_COMPRADOR)
    
    cat_selecionada = st.selectbox("Categoria *", opcoes_cat_manual)
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
        col_vt, col_vp = st.columns(2)
        valor_total_compra = col_vt.number_input("Valor TOTAL da Compra (R$) *", min_value=0.00, step=10.00, format="%.2f", key="g_val_parc_tot")
        valor_parcela = col_vp.number_input("Valor da PARCELA Mensal (R$) *", min_value=0.00, step=10.00, format="%.2f", key="g_val_parc_mensal")
        
        col_p1, col_p2 = st.columns(2)
        total_parcelas = col_p2.number_input("Quantidade Total de Parcelas *", min_value=2, value=2)
        parcela_atual = col_p1.number_input("Qual parcela é essa? *", min_value=1, value=1)
        
        # APLICANDO A FORMATAÇÃO BRASILEIRA NA MENSAGEM INFORMATIVA
        st.info(f"O valor de cada parcela será: **{formatar_moeda(valor_parcela)}**")
        
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
            
            for key in ['g_desc', 'g_val_vista', 'g_val_parc_tot', 'g_val_parc_mensal', 'g_cat_nova']:
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
                "id": None, 
                "mes_referencia": st.column_config.DateColumn("Data", format="DD/MM/YYYY"), 
                "usuario": st.column_config.SelectboxColumn("Pessoa", options=OPCOES_COMPRADOR[:2], required=True), 
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
                    if 'mes_referencia' in mudancas: mudancas['mes_referencia'] = mudancas['mes_referencia'] + "T00:00:00"
                    supabase.table("receitas").update(mudancas).eq("id", int(id_upd)).execute()
                fez_algo_r = True
            if fez_algo_r:
                st.success("Salários atualizados!")
                st.rerun()

# ------------------------------------------
# ABA 4: IMPORTAR FATURA
# ------------------------------------------
with aba_pdf:
    if 'fatura_em_revisao' not in st.session_state:
        st.subheader("Importar Fatura")
        st.write("A IA vai procurar a data exata de cada compra. A 'Data base' abaixo será usada só para compras onde a IA não achar a data.")
        dono_fatura = st.radio("Essa fatura é primariamente de quem?", OPCOES_COMPRADOR, key="dono_fat")
        data_fatura = st.date_input("Data base dessa fatura", value=date.today())
        arquivo_pdf = st.file_uploader("Escolha o arquivo PDF", type=["pdf"])
        
        if arquivo_pdf is not None and st.button("Analisar Fatura"):
            with st.spinner("A IA está analisando o PDF da sua fatura e lendo as datas..."):
                try:
                    pdf_bytes = arquivo_pdf.getvalue()
                    prompt = """
                    Leia a fatura de cartão anexada. Extraia APENAS as compras realizadas.
                    Ignore pagamentos de fatura, estornos, saldos anteriores ou encargos.
                    
                    Retorne EXCLUSIVAMENTE um array JSON. 
                    Cada objeto deve conter:
                    - "data_compra": (string, formato YYYY-MM-DD. Tente identificar a data exata da compra na fatura. Presuma o ano atual se não houver)
                    - "descricao": (string, nome do estabelecimento)
                    - "valor": (numero decimal, parcela do mês)
                    - "valor_total": (numero decimal, total da compra)
                    - "categoria": (string)
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
                        if not c.get("data_compra"):
                            c["data_compra"] = data_fatura.isoformat()
                    
                    st.session_state['fatura_em_revisao'] = compras_extraidas
                    st.session_state['fatura_data_base'] = data_fatura
                    st.rerun()
                except Exception as e:
                    st.error("Erro na leitura. Certifique-se de que é um PDF válido.")
                    st.error(f"Erro técnico: {e}")
                    
    else:
        st.subheader("🔍 Validação da Fatura")
        st.write("Dê dois cliques nas células para **alterar as Categorias ou os Compradores selecionando nas listas**, ajuste datas/valores ou exclua (Delete) o que não quiser salvar.")
        
        df_rev = pd.DataFrame(st.session_state['fatura_em_revisao'])
        
        col_nec = ['data_compra', 'descricao', 'valor', 'valor_total', 'categoria', 'comprador', 'parcela_atual', 'total_parcelas']
        for col in col_nec:
            if col not in df_rev.columns:
                if 'parcela' in col: df_rev[col] = 1
                elif 'valor' in col: df_rev[col] = 0.0
                elif col == 'comprador': df_rev[col] = OPCOES_COMPRADOR[0]
                elif col == 'data_compra': df_rev[col] = st.session_state['fatura_data_base']
                else: df_rev[col] = ""
                
        df_rev['data_compra'] = pd.to_datetime(df_rev['data_compra'], errors='coerce').dt.date
        df_rev['data_compra'] = df_rev['data_compra'].fillna(st.session_state['fatura_data_base'])
        
        opcoes_cat_fatura = categorias_banco.copy()
        for cat in df_rev['categoria'].dropna().unique():
            if cat not in opcoes_cat_fatura: opcoes_cat_fatura.append(cat)
                
        fatura_editada = st.data_editor(
            df_rev, 
            key="editor_fatura", 
            use_container_width=True, 
            num_rows="dynamic",
            column_config={
                "data_compra": st.column_config.DateColumn("Data da Compra", format="DD/MM/YYYY"),
                "descricao": st.column_config.TextColumn("Descrição da Compra"),
                "valor": st.column_config.NumberColumn("Valor PARCELA (R$)", format="%.2f"),
                "valor_total": st.column_config.NumberColumn("Valor TOTAL (R$)", format="%.2f"),
                "categoria": st.column_config.SelectboxColumn("Categoria", options=opcoes_cat_fatura, required=True),
                "comprador": st.column_config.SelectboxColumn("De quem é a conta?", options=OPCOES_COMPRADOR, required=True),
                "parcela_atual": st.column_config.NumberColumn("Parcela Nº", min_value=1),
                "total_parcelas": st.column_config.NumberColumn("Total Parcelas", min_value=1),
            }, 
            hide_index=True
        )
        
        st.divider()
        col_btn1, col_btn2 = st.columns(2)
        
        if col_btn1.button("✅ Confirmar e Salvar no Sistema", type="primary"):
            compras_finais = fatura_editada.to_dict('records')
            for c in compras_finais:
                data_final = c["data_compra"].isoformat() if hasattr(c["data_compra"], 'isoformat') else str(c["data_compra"])
                supabase.table("gastos").insert({
                    "conta_id": CONTA_ID,
                    "descricao": c["descricao"],
                    "valor": float(c["valor"]), 
                    "valor_total": float(c.get("valor_total", c["valor"])), 
                    "categoria": c["categoria"], 
                    "comprador": c["comprador"],
                    "data_compra": data_final,
                    "recorrente": False,
                    "parcela_atual": int(c.get("parcela_atual", 1)),
                    "total_parcelas": int(c.get("total_parcelas", 1))
                }).execute()
            
            del st.session_state['fatura_em_revisao']
            del st.session_state['fatura_data_base']
            st.success("Todas as compras validadas foram salvas com sucesso!")
            st.rerun()
            
        if col_btn2.button("❌ Cancelar Importação"):
            del st.session_state['fatura_em_revisao']
            del st.session_state['fatura_data_base']
            st.rerun()

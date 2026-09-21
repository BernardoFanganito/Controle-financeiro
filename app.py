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
# SISTEMA DE LOGIN / CADASTRO
# ==========================================
if 'conta_id' not in st.session_state:
    st.session_state['conta_id'] = None

if st.session_state['conta_id'] is None:
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
                st.session_state['nome_2'] = conta['nome_2'] # Ficará vazio se for conta individual
                st.success("Login efetuado com sucesso!")
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
                
    with aba_cadastro:
        tipo_conta = st.radio("Como você vai usar o sistema?", ["Em Casal", "Sozinho (Individual)"])
        novo_usuario = st.text_input("Crie um nome de Usuário (Ex: leticia_marcos ou leticia123)")
        nova_senha = st.text_input("Crie uma Senha", type="password")
        nome_1 = st.text_input("Seu Nome (Pessoa 1)")
        
        nome_2 = ""
        if tipo_conta == "Em Casal":
            nome_2 = st.text_input("Nome do Parceiro(a) (Pessoa 2)")
        
        if st.button("Criar Conta"):
            # Validação obrigatória
            if not novo_usuario or not nova_senha or not nome_1:
                st.warning("Preencha os campos obrigatórios (Usuário, Senha e Seu Nome)!")
            elif tipo_conta == "Em Casal" and not nome_2:
                st.warning("Preencha o nome da Pessoa 2 ou mude para uso 'Sozinho'!")
            else:
                try:
                    supabase.table("contas").insert({
                        "usuario": novo_usuario,
                        "senha": nova_senha,
                        "nome_1": nome_1,
                        "nome_2": nome_2
                    }).execute()
                    st.success("Conta criada! Volte na aba de Login para entrar.")
                except Exception as e:
                    st.error("Erro ao criar. Esse nome de usuário já deve existir.")
    st.stop()

# ==========================================
# INTERFACE DO SITE (LOGADO)
# ==========================================
CONTA_ID = st.session_state['conta_id']
NOME_USUARIO_1 = st.session_state['nome_1']
NOME_USUARIO_2 = st.session_state['nome_2']

# Define as opções baseado se é casal ou solteiro
if NOME_USUARIO_2 != "":
    OPCOES_COMPRADOR = [NOME_USUARIO_1, NOME_USUARIO_2, "Juntos (Dividido 50/50)"]
    MODO_CASAL = True
else:
    OPCOES_COMPRADOR = [NOME_USUARIO_1]
    MODO_CASAL = False

with st.sidebar:
    if MODO_CASAL:
        st.write(f"Bem-vindos, **{NOME_USUARIO_1} & {NOME_USUARIO_2}**! 👋")
    else:
        st.write(f"Bem-vinda(o), **{NOME_USUARIO_1}**! 👋")
        
    if st.button("Sair da Conta"):
        st.session_state.clear()
        st.rerun()

st.title("💸 Controle Financeiro")

aba_dashboard, aba_add_manual, aba_renda, aba_pdf = st.tabs([
    "📊 Visão e Edição", "✍️ Registrar Compra", "💰 Meus Salários (Sobra)", "📄 Importar Fatura"
])

# Busca os dados GERAIS da conta
resp_gastos = supabase.table("gastos").select("*").eq("conta_id", CONTA_ID).execute()
resp_rendas = supabase.table("receitas").select("*").eq("conta_id", CONTA_ID).execute()

df_gastos = pd.DataFrame(resp_gastos.data) if resp_gastos.data else pd.DataFrame()
df_rendas = pd.DataFrame(resp_rendas.data) if resp_rendas.data else pd.DataFrame()

# Tratamento base de datas
if not df_gastos.empty:
    df_gastos['data_compra'] = pd.to_datetime(df_gastos['data_compra'])
    df_gastos['mes_ano'] = df_gastos['data_compra'].dt.strftime('%Y-%m')
if not df_rendas.empty:
    df_rendas['mes_referencia'] = pd.to_datetime(df_rendas['mes_referencia'])
    df_rendas['mes_ano'] = df_rendas['mes_referencia'].dt.strftime('%Y-%m')

# ------------------------------------------
# ABA 1: DASHBOARD (Gráficos em Barra e Edição)
# ------------------------------------------
with aba_dashboard:
    if MODO_CASAL:
        visao = st.selectbox("De quem é a visão?", ["Visão Geral (Casal)", NOME_USUARIO_1, NOME_USUARIO_2])
    else:
        visao = NOME_USUARIO_1

    if not df_gastos.empty:
        # Filtro de Divisão (50/50)
        if visao == "Visão Geral (Casal)":
            df_filtrado = df_gastos.copy()
        elif visao in [NOME_USUARIO_1, NOME_USUARIO_2]:
            df_individual = df_gastos[df_gastos['comprador'] == visao].copy()
            df_juntos = df_gastos[df_gastos['comprador'] == "Juntos (Dividido 50/50)"].copy()
            df_juntos['valor'] = df_juntos['valor'] / 2 
            df_filtrado = pd.concat([df_individual, df_juntos])

        total_gasto = df_filtrado['valor'].sum()
        
        st.subheader(f"Resumo: {visao}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Gasto", f"R$ {total_gasto:.2f}")
        
        if not df_rendas.empty:
            if visao == "Visão Geral (Casal)":
                total_renda = df_rendas['valor'].sum()
            else:
                total_renda = df_rendas[df_rendas['usuario'] == visao]['valor'].sum()
            c2.metric("Renda Total", f"R$ {total_renda:.2f}")
            c3.metric("Saldo Sobrando", f"R$ {(total_renda - total_gasto):.2f}", delta=float(total_renda - total_gasto))
        
        st.divider()

        # Gráficos em Barras Padrão
        col_graf1, col_graf2 = st.columns(2)
        with col_graf1:
            st.write("### 📈 Gastos por Mês")
            # Configuração limpa para garantir gráfico de barras
            grafico_mes = df_filtrado.groupby('mes_ano', as_index=False)['valor'].sum()
            st.bar_chart(grafico_mes, x="mes_ano", y="valor")
            
        with col_graf2:
            st.write("### 🍕 Gastos por Categoria")
            grafico_cat = df_filtrado.groupby('categoria', as_index=False)['valor'].sum()
            st.bar_chart(grafico_cat, x="categoria", y="valor")

        # HISTÓRICO EDITÁVEL
        st.write("### ✏️ Histórico (Dê dois cliques para editar)")
        
        # Prepara a tabela escondendo o ID visualmente
        df_exibicao = df_filtrado[['id', 'data_compra', 'descricao', 'valor', 'categoria', 'comprador', 'parcela_atual', 'total_parcelas']].copy()
        df_exibicao['data_compra'] = df_exibicao['data_compra'].dt.date
        
        # O data_editor permite alterar tudo. A chave "editor_gastos" guarda as mudanças
        editado = st.data_editor(
            df_exibicao, 
            key="editor_gastos", 
            use_container_width=True,
            column_config={
                "id": None, # Esconde a coluna ID do usuário
                "data_compra": st.column_config.DateColumn("Data"),
                "descricao": st.column_config.TextColumn("Descrição"),
                "valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f"),
                "categoria": st.column_config.TextColumn("Categoria"),
            },
            hide_index=True
        )

        # Botão para salvar as edições
        if st.button("Salvar Edições"):
            alteracoes = st.session_state.editor_gastos.get("edited_rows", {})
            if alteracoes:
                try:
                    for row_idx, mudancas in alteracoes.items():
                        id_gasto = df_exibicao.iloc[row_idx]['id']
                        # Atualiza no banco só o que foi modificado
                        supabase.table("gastos").update(mudancas).eq("id", int(id_gasto)).execute()
                    st.success("Alterações salvas! A página vai recarregar.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
            else:
                st.info("Nenhuma edição feita.")
    else:
        st.info("Nenhum gasto registrado ainda.")

# ------------------------------------------
# ABA 2: ADICIONAR GASTO MANUAL (Limpa a tela e Valida)
# ------------------------------------------
with aba_add_manual:
    st.subheader("Registrar Nova Compra")
    
    # clear_on_submit=True faz a tela limpar sozinha após salvar
    with st.form("form_novo_gasto", clear_on_submit=True):
        desc = st.text_input("O que foi comprado? * (Obrigatório)")
        valor = st.number_input("Valor (R$) *", min_value=0.00, step=10.00, format="%.2f")
        
        data_compra = st.date_input("Data da Compra *", value=date.today())
        comprador = st.radio("De quem é essa conta? *", OPCOES_COMPRADOR)
        
        categorias_padrao = ["Comida/Mercado", "Compras Gerais", "Aluguel", "Casa/Doméstico", "Viagem", "Lazer/Saídas", "Outros"]
        cat_selecionada = st.selectbox("Categoria *", categorias_padrao)
        
        categoria_final = st.text_input("Se 'Outros', qual a categoria?") if cat_selecionada == "Outros" else cat_selecionada
            
        col_p1, col_p2 = st.columns(2)
        parcela_atual = col_p1.number_input("Parcela Atual *", min_value=1, value=1)
        total_parcelas = col_p2.number_input("Total de Parcelas *", min_value=1, value=1)
        recorrente = st.checkbox("Compra recorrente mensal?")
        
        enviou = st.form_submit_button("Salvar Gasto")
        
        if enviou:
            # TRAVAS DE SEGURANÇA (Campos obrigatórios)
            if not desc.strip():
                st.error("Erro: Você precisa digitar o que foi comprado.")
            elif valor <= 0:
                st.error("Erro: O valor deve ser maior que zero.")
            elif cat_selecionada == "Outros" and not categoria_final.strip():
                st.error("Erro: Você escolheu 'Outros', por favor digite o nome da categoria.")
            else:
                novo_gasto = {
                    "conta_id": CONTA_ID,
                    "descricao": desc,
                    "valor": float(valor),
                    "categoria": categoria_final,
                    "comprador": comprador,
                    "data_compra": data_compra.isoformat(),
                    "recorrente": recorrente,
                    "parcela_atual": int(parcela_atual),
                    "total_parcelas": int(total_parcelas)
                }
                supabase.table("gastos").insert(novo_gasto).execute()
                st.success(f"Gasto '{desc}' salvo! (O formulário foi limpo para a próxima)")
                st.rerun()

# ------------------------------------------
# ABA 3: RENDAS, HISTÓRICO E SOBRAS
# ------------------------------------------
with aba_renda:
    st.subheader("💰 Controle de Salários e Sobras")
    
    # Formulário que limpa sozinho
    with st.form("form_renda", clear_on_submit=True):
        usuario_renda = st.selectbox("Quem recebeu?", OPCOES_COMPRADOR[:2]) # Impede a opção "Juntos"
        mes_renda = st.date_input("Data do Recebimento", value=date.today())
        valor_renda = st.number_input("Valor Recebido (R$)", min_value=0.00, step=100.00, format="%.2f", help="Digite 3600.00 sem pontos nos milhares.")
        salvar_renda = st.form_submit_button("Salvar Salário")
        
        if salvar_renda:
            if valor_renda <= 0:
                st.error("O valor precisa ser maior que zero.")
            else:
                supabase.table("receitas").insert({
                    "conta_id": CONTA_ID,
                    "usuario": usuario_renda,
                    "mes_referencia": mes_renda.isoformat(),
                    "valor": float(valor_renda)
                }).execute()
                st.success("Salário cadastrado!")
                st.rerun()

    st.divider()
    
    # Análise de Sobra de Dinheiro
    if not df_rendas.empty and not df_gastos.empty:
        st.write("### 📈 Acompanhamento: Salário vs Sobra por Mês")
        
        # Agrupa salários por mês
        df_renda_mensal = df_rendas.groupby('mes_ano', as_index=False)['valor'].sum()
        df_renda_mensal.rename(columns={'valor': 'Salário Total'}, inplace=True)
        
        # Agrupa gastos totais por mês
        df_gasto_mensal = df_gastos.groupby('mes_ano', as_index=False)['valor'].sum()
        df_gasto_mensal.rename(columns={'valor': 'Gasto Total'}, inplace=True)
        
        # Junta os dois para calcular a sobra
        df_analise = pd.merge(df_renda_mensal, df_gasto_mensal, on='mes_ano', how='outer').fillna(0)
        df_analise['Sobra (Lucro)'] = df_analise['Salário Total'] - df_analise['Gasto Total']
        
        # Mostra gráfico das Sobras
        st.bar_chart(df_analise, x="mes_ano", y=["Salário Total", "Gasto Total", "Sobra (Lucro)"])
        
        # Tabela Histórica
        st.write("### 🧾 Histórico de Recebimentos")
        df_rendas_exib = df_rendas[['mes_referencia', 'usuario', 'valor']].copy()
        df_rendas_exib['mes_referencia'] = df_rendas_exib['mes_referencia'].dt.date
        st.dataframe(df_rendas_exib.sort_values(by="mes_referencia", ascending=False), hide_index=True, use_container_width=True)
        
    elif not df_rendas.empty:
         st.write("### 🧾 Histórico de Recebimentos")
         st.dataframe(df_rendas[['mes_referencia', 'usuario', 'valor']], hide_index=True)
    else:
        st.info("Cadastre salários e despesas para ver seu gráfico de lucros e sobras aqui.")

# ------------------------------------------
# ABA 4: IMPORTAR FATURA (PDF)
# ------------------------------------------
with aba_pdf:
    st.subheader("Importar Fatura (Leitura por IA)")
    dono_fatura = st.radio("Essa fatura é de quem?", OPCOES_COMPRADOR, key="dono_fat")
    data_fatura = st.date_input("Data base dessa fatura", value=date.today())
    arquivo_pdf = st.file_uploader("Escolha o arquivo PDF", type=["pdf"])
    
    if arquivo_pdf is not None:
        if st.button("Analisar Fatura"):
            with st.spinner("Lendo sua fatura..."):
                leitor = PyPDF2.PdfReader(arquivo_pdf)
                texto_fatura = "".join([p.extract_text() for p in leitor.pages])
                prompt = f"""
                Leia a fatura de cartão. Extraia apenas as compras realizadas.
                Retorne APENAS um array JSON válido. Cada objeto deve ter:
                "descricao" (string), "valor" (numero decimal), 
                "categoria" (string), "parcela_atual" (inteiro), "total_parcelas" (inteiro).
                Fatura: {texto_fatura}
                """
                try:
                    resposta_ia = modelo_ia.generate_content(prompt)
                    texto_json = resposta_ia.text.strip().removeprefix('```json').removesuffix('```').strip()
                    compras = json.loads(texto_json)
                    st.write(f"Encontrei {len(compras)} compras!")
                    for c in compras:
                        supabase.table("gastos").insert({
                            "conta_id": CONTA_ID,
                            "descricao": c["descricao"],
                            "valor": c["valor"],
                            "categoria": c["categoria"],
                            "comprador": dono_fatura,
                            "data_compra": data_fatura.isoformat(),
                            "recorrente": False,
                            "parcela_atual": c.get("parcela_atual", 1),
                            "total_parcelas": c.get("total_parcelas", 1)
                        }).execute()
                    st.success("Tudo salvo!")
                except Exception as e:
                    st.error(f"Erro ao processar: {e}")

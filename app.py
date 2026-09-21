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
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)
modelo_ia = genai.GenerativeModel('gemini-1.5-flash')

# Nomes dos usuários
NOME_USUARIO_1 = "Bernardo"
NOME_USUARIO_2 = "Você" # <-- MUDE PARA O SEU NOME AQUI
OPCOES_COMPRADOR = [NOME_USUARIO_1, NOME_USUARIO_2, "Juntos (Dividido 50/50)"]

# ==========================================
# INTERFACE DO SITE
# ==========================================
st.set_page_config(page_title="Controle Financeiro", page_icon="💸", layout="wide")
st.title("💸 Controle Financeiro Inteligente")

# Abas atualizadas
aba_dashboard, aba_add_manual, aba_pdf, aba_renda = st.tabs([
    "📊 Dashboard", "✍️ Adicionar Gasto", "📄 Importar Fatura", "💰 Salários/Rendas"
])

# ------------------------------------------
# ABA 1: DASHBOARD (Gráficos e Visões)
# ------------------------------------------
with aba_dashboard:
    col1, col2 = st.columns([1, 2])
    visao = col1.selectbox("De quem é a visão?", ["Visão Geral (Casal)", NOME_USUARIO_1, NOME_USUARIO_2])
    
    # Buscando dados
    resp_gastos = supabase.table("gastos").select("*").execute()
    resp_rendas = supabase.table("receitas").select("*").execute()
    
    df_gastos = pd.DataFrame(resp_gastos.data) if resp_gastos.data else pd.DataFrame()
    df_rendas = pd.DataFrame(resp_rendas.data) if resp_rendas.data else pd.DataFrame()

    if not df_gastos.empty:
        # Tratando datas
        df_gastos['data_compra'] = pd.to_datetime(df_gastos['data_compra'])
        df_gastos['mes_ano'] = df_gastos['data_compra'].dt.strftime('%Y-%m')
        
        # Filtro de Visão (O Segredo da Divisão 50/50)
        if visao == "Visão Geral (Casal)":
            df_filtrado = df_gastos.copy()
        else:
            # Pega os gastos individuais + metade dos gastos juntos
            df_individual = df_gastos[df_gastos['comprador'] == visao].copy()
            df_juntos = df_gastos[df_gastos['comprador'] == "Juntos (Dividido 50/50)"].copy()
            df_juntos['valor'] = df_juntos['valor'] / 2  # Divide o valor pela metade
            df_filtrado = pd.concat([df_individual, df_juntos])

        total_gasto = df_filtrado['valor'].sum()
        
        # Resumo de Renda vs Gasto
        st.subheader(f"Resumo: {visao}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Gasto Registrado", f"R$ {total_gasto:.2f}")
        
        if not df_rendas.empty:
            if visao == "Visão Geral (Casal)":
                total_renda = df_rendas['valor'].sum()
            else:
                total_renda = df_rendas[df_rendas['usuario'] == visao]['valor'].sum()
                
            c2.metric("Renda Total Registrada", f"R$ {total_renda:.2f}")
            saldo = total_renda - total_gasto
            c3.metric("Saldo Sobrando", f"R$ {saldo:.2f}", delta=float(saldo))
        
        st.divider()

        # Gráficos
        col_graf1, col_graf2 = st.columns(2)
        
        with col_graf1:
            st.write("### 📈 Gastos por Mês")
            gastos_por_mes = df_filtrado.groupby('mes_ano')['valor'].sum().reset_index()
            st.bar_chart(gastos_por_mes.set_index('mes_ano'))
            
        with col_graf2:
            st.write("### 🍕 Gastos por Categoria")
            gastos_por_cat = df_filtrado.groupby('categoria')['valor'].sum().reset_index()
            st.bar_chart(gastos_por_cat.set_index('categoria'))

        st.write("### 🛒 Histórico de Compras")
        st.dataframe(df_filtrado[['data_compra', 'descricao', 'valor', 'categoria', 'comprador']].sort_values(by="data_compra", ascending=False), use_container_width=True)

    else:
        st.info("Nenhum gasto registrado ainda.")

# ------------------------------------------
# ABA 2: ADICIONAR GASTO MANUAL
# ------------------------------------------
with aba_add_manual:
    st.subheader("Registrar Compra")
    with st.form("form_novo_gasto"):
        desc = st.text_input("O que foi comprado?")
        valor = st.number_input("Valor (R$)", min_value=0.01, format="%.2f")
        
        # Data Retroativa
        data_compra = st.date_input("Data da Compra", value=date.today())
        
        # Quem pagou / Divisão
        comprador = st.radio("De quem é essa conta?", OPCOES_COMPRADOR)
        
        # Categoria Dinâmica
        categorias_padrao = ["Comida/Mercado", "Compras Gerais", "Aluguel", "Casa/Doméstico", "Viagem", "Lazer/Saídas", "Outros"]
        cat_selecionada = st.selectbox("Categoria", categorias_padrao)
        
        # Se escolher outros, abre campo de texto
        if cat_selecionada == "Outros":
            categoria_final = st.text_input("Qual categoria? (Ex: Carro, Gata, etc.)")
        else:
            categoria_final = cat_selecionada
            
        col_p1, col_p2 = st.columns(2)
        parcela_atual = col_p1.number_input("Parcela Atual", min_value=1, value=1)
        total_parcelas = col_p2.number_input("Total de Parcelas", min_value=1, value=1)
        recorrente = st.checkbox("Compra recorrente mensal? (Ex: Conta de luz, Netflix)")
        
        enviou = st.form_submit_button("Salvar Gasto")
        
        if enviou:
            if cat_selecionada == "Outros" and not categoria_final:
                st.error("Por favor, digite o nome da categoria!")
            else:
                novo_gasto = {
                    "descricao": desc,
                    "valor": float(valor),
                    "categoria": categoria_final,
                    "comprador": comprador,
                    "data_compra": data_compra.isoformat(),
                    "recorrente": recorrente,
                    "parcela_atual": parcela_atual,
                    "total_parcelas": total_parcelas
                }
                supabase.table("gastos").insert(novo_gasto).execute()
                st.success("Gasto salvo com sucesso!")
                st.rerun()

# ------------------------------------------
# ABA 3: IMPORTAR FATURA (PDF)
# ------------------------------------------
with aba_pdf:
    st.subheader("Importar Fatura (Leitura por IA)")
    st.write("A IA vai ler o PDF e cadastrar as compras automaticamente.")
    
    # Definir de quem é a fatura
    dono_fatura = st.radio("Essa fatura é de quem?", OPCOES_COMPRADOR, key="dono_fat")
    data_fatura = st.date_input("Data base dessa fatura (Retroativa ou Atual)", value=date.today())
    
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
                "categoria" (string, classifique em: Comida, Compras, Casa, Viagem, Lazer, ou crie uma se precisar),
                "parcela_atual" (inteiro), "total_parcelas" (inteiro).
                Fatura: {texto_fatura}
                """
                try:
                    resposta_ia = modelo_ia.generate_content(prompt)
                    texto_json = resposta_ia.text.strip().removeprefix('```json').removesuffix('```').strip()
                    compras = json.loads(texto_json)
                    
                    st.write(f"Encontrei {len(compras)} compras!")
                    st.json(compras)
                    
                    for c in compras:
                        novo_dado = {
                            "descricao": c["descricao"],
                            "valor": c["valor"],
                            "categoria": c["categoria"],
                            "comprador": dono_fatura,
                            "data_compra": data_fatura.isoformat(),
                            "recorrente": False,
                            "parcela_atual": c.get("parcela_atual", 1),
                            "total_parcelas": c.get("total_parcelas", 1)
                        }
                        supabase.table("gastos").insert(novo_dado).execute()
                    
                    st.success("Tudo salvo!")
                except Exception as e:
                    st.error(f"Erro ao processar: {e}")

# ------------------------------------------
# ABA 4: SALÁRIOS E RENDAS
# ------------------------------------------
with aba_renda:
    st.subheader("Adicionar Renda / Salário")
    st.write("Cadastre o quanto vocês ganharam no mês para comparar com os gastos.")
    
    with st.form("form_renda"):
        usuario_renda = st.selectbox("Quem recebeu?", [NOME_USUARIO_1, NOME_USUARIO_2])
        mes_renda = st.date_input("Mês de Referência (Selecione qualquer dia do mês)", value=date.today())
        valor_renda = st.number_input("Valor Recebido (R$)", min_value=0.01, format="%.2f")
        
        salvar_renda = st.form_submit_button("Salvar Renda")
        
        if salvar_renda:
            nova_renda = {
                "usuario": usuario_renda,
                "mes_referencia": mes_renda.isoformat(),
                "valor": float(valor_renda)
            }
            supabase.table("receitas").insert(nova_renda).execute()
            st.success("Renda cadastrada!")
            st.rerun()

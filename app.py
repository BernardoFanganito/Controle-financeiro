import streamlit as st
import google.generativeai as genai
from supabase import create_client
import PyPDF2
import json
import pandas as pd
from datetime import datetime

# ==========================================
# CONFIGURAÇÕES DE SEGURANÇA E CONEXÕES
# ==========================================
# O Streamlit vai pegar essas chaves de um arquivo seguro que vamos configurar na hospedagem
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

# Conectando ao Banco de Dados e à IA
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)
modelo_ia = genai.GenerativeModel('gemini-1.5-flash')

# ==========================================
# INTERFACE DO SITE
# ==========================================
st.set_page_config(page_title="Nosso Controle Financeiro", page_icon="💸", layout="centered")
st.title("💸 Controle Financeiro do Casal")

# Criando abas para organizar o site
aba_dashboard, aba_add_manual, aba_pdf = st.tabs(["📊 Visão Geral", "✍️ Adicionar Gasto", "📄 Importar Fatura (PDF)"])

# ------------------------------------------
# ABA 1: DASHBOARD (VISÃO GERAL)
# ------------------------------------------
with aba_dashboard:
    st.subheader("Resumo de Gastos")
    
    # Busca os dados no banco
    resposta = supabase.table("gastos").select("*").execute()
    dados = resposta.data
    
    if dados:
        df = pd.DataFrame(dados)
        
        col1, col2 = st.columns(2)
        total_gasto = df['valor'].sum()
        col1.metric("Total Gasto (Geral)", f"R$ {total_gasto:.2f}")
        
        # Mostrando as parcelas pendentes
        df_parcelado = df[df['total_parcelas'] > 1]
        st.write("### 🗓️ Controle de Parcelas")
        if not df_parcelado.empty:
            for index, row in df_parcelado.iterrows():
                falta = row['total_parcelas'] - row['parcela_atual']
                st.info(f"**{row['descricao']}**: Parcela {row['parcela_atual']}/{row['total_parcelas']} (Faltam {falta} parcelas de R$ {row['valor']:.2f})")
        
        st.write("### 🛒 Detalhamento")
        st.dataframe(df[['descricao', 'valor', 'categoria', 'comprador', 'data_compra']], use_container_width=True)
    else:
        st.write("Nenhum gasto registrado ainda. Comece a adicionar!")

# ------------------------------------------
# ABA 2: ADICIONAR MANUALMENTE
# ------------------------------------------
with aba_add_manual:
    st.subheader("Novo Gasto")
    with st.form("form_novo_gasto"):
        desc = st.text_input("O que foi comprado?")
        valor = st.number_input("Valor (R$)", min_value=0.01, format="%.2f")
        categoria = st.selectbox("Categoria", ["Mercado", "Lazer", "Casa", "Ifood", "Transporte", "Outros"])
        comprador = st.radio("Quem comprou?", ["Eu", "Namorado"])
        
        col_p1, col_p2 = st.columns(2)
        parcela_atual = col_p1.number_input("Parcela Atual", min_value=1, value=1)
        total_parcelas = col_p2.number_input("Total de Parcelas", min_value=1, value=1)
        recorrente = st.checkbox("É uma compra recorrente mensal? (Ex: Netflix)")
        
        enviou = st.form_submit_button("Salvar Gasto")
        
        if enviou:
            novo_gasto = {
                "descricao": desc,
                "valor": float(valor),
                "categoria": categoria,
                "comprador": comprador,
                "data_compra": datetime.now().isoformat(),
                "recorrente": recorrente,
                "parcela_atual": parcela_atual,
                "total_parcelas": total_parcelas
            }
            supabase.table("gastos").insert(novo_gasto).execute()
            st.success("Gasto salvo com sucesso!")
            st.rerun()

# ------------------------------------------
# ABA 3: IMPORTAR FATURA (IA)
# ------------------------------------------
with aba_pdf:
    st.subheader("Importar Fatura de Cartão (Leitura por IA)")
    st.write("Suba o PDF da sua fatura e a IA vai separar as compras por categoria, identificar parcelas e valores.")
    
    arquivo_pdf = st.file_uploader("Escolha o arquivo PDF", type=["pdf"])
    
    if arquivo_pdf is not None:
        if st.button("Analisar Fatura"):
            with st.spinner("A IA está lendo sua fatura... Isso pode levar alguns segundos."):
                # 1. Extraindo texto do PDF
                leitor = PyPDF2.PdfReader(arquivo_pdf)
                texto_fatura = ""
                for pagina in leitor.pages:
                    texto_fatura += pagina.extract_text()
                
                # 2. Pedindo para a IA analisar
                prompt = f"""
                Você é um assistente financeiro. Leia o texto desta fatura de cartão de crédito e extraia apenas as compras realizadas.
                Ignora pagamentos da fatura anterior.
                Retorne APENAS um array JSON válido, sem formatação markdown e sem explicações, onde cada objeto tenha:
                "descricao" (string, nome do estabelecimento),
                "valor" (numero decimal, usando ponto),
                "categoria" (string, tente adivinhar o tipo de estabelecimento: Mercado, Restaurante, Transporte, Saúde, etc),
                "parcela_atual" (numero inteiro. Se não for parcelado, é 1),
                "total_parcelas" (numero inteiro. Se não for parcelado, é 1)
                
                Texto da Fatura:
                {texto_fatura}
                """
                
                try:
                    resposta_ia = modelo_ia.generate_content(prompt)
                    # Limpando a resposta para garantir que seja JSON
                    texto_json = resposta_ia.text.strip().removeprefix('```json').removesuffix('```').strip()
                    compras = json.loads(texto_json)
                    
                    st.write(f"Encontrei {len(compras)} compras!")
                    st.json(compras)
                    
                    # Salvando no banco
                    for c in compras:
                        novo_dado = {
                            "descricao": c["descricao"],
                            "valor": c["valor"],
                            "categoria": c["categoria"],
                            "comprador": "Fatura Importada",
                            "data_compra": datetime.now().isoformat(),
                            "recorrente": False,
                            "parcela_atual": c.get("parcela_atual", 1),
                            "total_parcelas": c.get("total_parcelas", 1)
                        }
                        supabase.table("gastos").insert(novo_dado).execute()
                    
                    st.success("Tudo salvo no banco de dados!")
                
                except Exception as e:
                    st.error(f"Ocorreu um erro ao processar. Tente novamente. Erro: {e}")

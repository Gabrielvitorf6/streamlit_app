import pandas as pd
import streamlit as st
import plotly.express as px
from fpdf import FPDF
import tempfile
import os

st.set_page_config(page_title="Dashboard Interativo DRE", layout="wide")

# 1. SISTEMA DE LOGIN DE USUÁRIO
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False


def tela_login():
    st.title("Acesso ao Painel DRE")

    with st.form("login_form"):
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        submit = st.form_submit_button("Entrar")

        if submit:
            if usuario == "Admin" and senha == "admin123":
                st.session_state['autenticado'] = True
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")


if not st.session_state['autenticado']:
    tela_login()
    st.stop()

# 2. CARREGAMENTO DE DADOS
ARQUIVO_PADRAO = "DRE 2019.xlsx"


@st.cache_data
def carregar_dados(arquivo):
    plano = pd.read_excel(arquivo, sheet_name="Plano de Contas")
    realizado = pd.read_excel(arquivo, sheet_name="Realizado")
    orcado = pd.read_excel(arquivo, sheet_name="Orçado")

    realizado["Conta"] = realizado["Conta"].astype(str)
    orcado["Conta"] = orcado["Conta"].astype(str)
    plano["Conta"] = plano["Conta"].astype(str)

    realizado["Mês/Ano"] = pd.to_datetime(realizado["Mês/Ano"])
    orcado["Mês/Ano"] = pd.to_datetime(orcado["Mês/Ano"])

    df_real = realizado.merge(plano, on="Conta", how="left")
    df_orc = orcado.merge(plano, on="Conta", how="left")

    df_real["Tipo"] = "Realizado"
    df_orc["Tipo"] = "Orçado"

    df_real = df_real.rename(columns={"Valor Realizado": "Valor"})
    df_orc = df_orc.rename(columns={"Valor Orçado": "Valor"})

    df = pd.concat([df_real, df_orc], ignore_index=True)
    df["Ano"] = df["Mês/Ano"].dt.year
    df["Mes"] = df["Mês/Ano"].dt.month
    df["Mes_Nome"] = df["Mês/Ano"].dt.strftime("%b/%Y")

    return df


st.title("Dashboard Interativo de Análise de Dados")
st.caption("O usuário escolhe dimensões, métricas e tipo de gráfico a partir das tabelas do Excel.")

with st.sidebar:
    st.header("Configurações")
    arquivo = st.file_uploader(
        "Envie um arquivo Excel",
        type=["xlsx"],
        help="Se nada for enviado, o app tenta abrir o arquivo DRE 2019.xlsx na mesma pasta."
    )
    if st.button("Sair (Logout)"):
        st.session_state['autenticado'] = False
        st.rerun()

if arquivo is not None:
    df = carregar_dados(arquivo)
else:
    df = carregar_dados(ARQUIVO_PADRAO)

st.subheader("Pré-visualização dos dados")
st.dataframe(df.head(20), use_container_width=True)

# 3. FILTROS E AGRUPAMENTOS
st.sidebar.header("Filtros")
tipos = st.sidebar.multiselect("Tipo", sorted(df["Tipo"].dropna().unique()),
                               default=sorted(df["Tipo"].dropna().unique()))
n1 = st.sidebar.multiselect("Nível 1", sorted(df["Nível 1"].dropna().unique()),
                            default=sorted(df["Nível 1"].dropna().unique()))
n2 = st.sidebar.multiselect("Nível 2", sorted(df["Nível 2"].dropna().unique()),
                            default=sorted(df["Nível 2"].dropna().unique()))
contas = st.sidebar.multiselect("Conta / Descrição", sorted(df["Descrição da Conta"].dropna().unique()))

anos = sorted(df["Ano"].dropna().unique())
anos_sel = st.sidebar.multiselect("Ano", anos, default=anos)

df_f = df.copy()
df_f = df_f[df_f["Tipo"].isin(tipos)]
df_f = df_f[df_f["Nível 1"].isin(n1)]
df_f = df_f[df_f["Nível 2"].isin(n2)]
df_f = df_f[df_f["Ano"].isin(anos_sel)]
if contas:
    df_f = df_f[df_f["Descrição da Conta"].isin(contas)]

st.sidebar.header("Montagem do gráfico")
dimensoes = {
    "Mês/Ano": "Mes_Nome",
    "Conta": "Conta",
    "Descrição da Conta": "Descrição da Conta",
    "Nível 1": "Nível 1",
    "Nível 2": "Nível 2",
    "Tipo": "Tipo",
    "Ano": "Ano",
    "Mês": "Mes",
}
x_label = st.sidebar.selectbox("Eixo X", list(dimensoes.keys()), index=0)
cor_label = st.sidebar.selectbox("Cor / Série", ["Nenhuma"] + list(dimensoes.keys()), index=5)
grafico = st.sidebar.selectbox("Tipo de gráfico", ["Barra", "Linha", "Pizza", "Área"])
agregacao = st.sidebar.selectbox("Agregação", ["Soma", "Média", "Contagem"])

# 4. MÉTRICAS
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Registros filtrados", f"{len(df_f):,}".replace(",", "."))
with col2:
    st.metric("Valor total", f"R$ {df_f['Valor'].sum():,.0f}".replace(",", "X").replace(".", ",").replace("X", "."))
with col3:
    st.metric("Média", f"R$ {df_f['Valor'].mean():,.0f}".replace(",", "X").replace(".", ",").replace("X", "."))
with col4:
    st.metric("Qtd. contas", int(df_f["Conta"].nunique()))

if df_f.empty:
    st.warning("Nenhum dado encontrado com os filtros escolhidos.")
    st.stop()

# 5. GRÁFICO DINÂMICO
x = dimensoes[x_label]
cor = None if cor_label == "Nenhuma" else dimensoes[cor_label]

if agregacao == "Soma":
    df_plot = df_f.groupby([x] + ([cor] if cor else []), dropna=False, as_index=False)["Valor"].sum()
    titulo_y = "Soma do Valor"
elif agregacao == "Média":
    df_plot = df_f.groupby([x] + ([cor] if cor else []), dropna=False, as_index=False)["Valor"].mean()
    titulo_y = "Média do Valor"
else:
    df_plot = df_f.groupby([x] + ([cor] if cor else []), dropna=False, as_index=False)["Valor"].count()
    titulo_y = "Contagem"
    df_plot = df_plot.rename(columns={"Valor": "Contagem"})

st.subheader("Gráfico dinâmico")

if grafico == "Barra":
    if agregacao == "Contagem":
        fig_main = px.bar(df_plot, x=x, y="Contagem", color=cor, barmode="group", title="Gráfico de barras")
    else:
        fig_main = px.bar(df_plot, x=x, y="Valor", color=cor, barmode="group", title="Gráfico de barras")
elif grafico == "Linha":
    if agregacao == "Contagem":
        fig_main = px.line(df_plot, x=x, y="Contagem", color=cor, markers=True, title="Gráfico de linhas")
    else:
        fig_main = px.line(df_plot, x=x, y="Valor", color=cor, markers=True, title="Gráfico de linhas")
elif grafico == "Pizza":
    base_pizza = df_plot.groupby(x, as_index=False)[df_plot.columns[-1]].sum()
    fig_main = px.pie(base_pizza, names=x, values=base_pizza.columns[-1], title="Gráfico de pizza")
else:
    if agregacao == "Contagem":
        fig_main = px.area(df_plot, x=x, y="Contagem", color=cor, title="Gráfico de área")
    else:
        fig_main = px.area(df_plot, x=x, y="Valor", color=cor, title="Gráfico de área")

fig_main.update_layout(xaxis_title=x_label, yaxis_title=titulo_y)
st.plotly_chart(fig_main, use_container_width=True)

# 6. QUADRO COMPARATIVO E DETECÇÃO DE PERDAS
st.subheader("Quadro Comparativo: Orçado vs Realizado")

df_comp = df_f.groupby([x, "Tipo"], as_index=False)["Valor"].sum()
df_pivot = df_comp.pivot(index=x, columns="Tipo", values="Valor").fillna(0).reset_index()

fig_comp = None
if "Realizado" in df_pivot.columns and "Orçado" in df_pivot.columns:
    df_pivot["Variação"] = df_pivot["Realizado"] - df_pivot["Orçado"]
    df_pivot["Status"] = df_pivot["Variação"].apply(lambda v: "Perda/Abaixo" if v < 0 else "Ganho/Acima")

    fig_comp = px.bar(
        df_pivot,
        x=x,
        y="Variação",
        color="Status",
        color_discrete_map={"Perda/Abaixo": "red", "Ganho/Acima": "green"},
        title="Detecção de Perdas (Realizado - Orçado)"
    )
    st.plotly_chart(fig_comp, use_container_width=True)

# 7. TABELAS E EXPORTAÇÃO
st.subheader("Tabela resumida")
st.dataframe(df_plot, use_container_width=True)

col_download_csv, col_download_pdf = st.columns(2)

with col_download_csv:
    csv = df_plot.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ Baixar tabela resumida em CSV",
        data=csv,
        file_name="resumo_dashboard.csv",
        mime="text/csv",
    )

with col_download_pdf:
    def gerar_pdf_report():
        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, "Relatorio de Desempenho DRE", ln=True, align='C')
        pdf.ln(10)

        pdf.set_font("Arial", '', 12)
        pdf.cell(0, 8, f"Eixo Analisado: {x_label}", ln=True)
        pdf.cell(0, 8, f"Registros Analisados: {len(df_f)}", ln=True)
        pdf.cell(0, 8,
                 f"Valor Total Encontrado: R$ {df_f['Valor'].sum():,.2f}".replace(",", "X").replace(".", ",").replace(
                     "X", "."), ln=True)
        pdf.ln(10)

        figs_to_export = [fig_main]
        if fig_comp is not None:
            figs_to_export.append(fig_comp)

        for fig in figs_to_export:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
                # O motor Kaleido requer que uma string seja passada para write_image
                fig.write_image(tmpfile.name, format="png", engine="kaleido")
                pdf.image(tmpfile.name, w=190)

            # CORREÇÃO AQUI: A deleção acontece APÓS o arquivo ser fechado pelo 'with'
            os.unlink(tmpfile.name)

        return pdf.output(dest='S').encode('latin-1')


    pdf_data = gerar_pdf_report()
    st.download_button(
        "📄 Exportar visualização como PDF",
        data=pdf_data,
        file_name="painel_dre.pdf",
        mime="application/pdf",
    )

with st.expander("Como este dashboard funciona"):
    st.markdown(
        """
        - Lê as abas **Plano de Contas**, **Realizado** e **Orçado**
        - Junta as tabelas pela coluna **Conta**
        - Permite filtrar por tipo, nível, conta e ano
        - O usuário escolhe:
          - eixo X
          - série/cor
          - tipo de gráfico
          - agregação
        - Gera tabela resumida e gráfico automaticamente
        - Autenticação de usuário para acesso
        - Quadro comparativo com detecção de perdas
        - Exportação da visualização para PDF
        """
    )

    #Comentário pra testar commit + push
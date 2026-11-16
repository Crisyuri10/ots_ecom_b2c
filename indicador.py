"""
Indicador SLA OTS E-commerce (publicado no Streamlit Cloud).

Lê o Google Sheets que a automação do computador (pasta app_sla_ecom) atualiza:
    aba "ano"       -> resumo por dia (cards e gráficos)
    aba "dados_sla" -> pedido a pedido (tabela)
Esta pasta é tudo o que vai para o GitHub: não tem chave nem dado de pedido.
No computador, a página pages/1_Indicador.py do app da automação abre este mesmo arquivo.

% OTS = ots_sim / ots_total (todos os pedidos, inclusive os em aberto).
"""
import os

import altair as alt
import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

# =========================
# PLANILHA (a mesma do base_config.py da automação; se trocar lá, trocar aqui)
# =========================
PLANILHA_ID = "1zdHB-SQsjpiJ1yO59lOlvma7IUCGy0WVdMKwO_Y1IfY"
ABA_RESUMO = "ano"
ABA_PEDIDOS = "dados_sla"
COLUNAS_STATUS = ["ots_sim", "ots_nao", "em_aberto", "ots_total"]

PASTA = os.path.dirname(os.path.abspath(__file__))
# Chave do Google: no Streamlit Cloud vem dos Secrets (seção [gcp_service_account]);
# no computador, do credenciais.json da pasta da automação (um nível acima desta pasta)
CREDENCIAIS_LOCAL = os.path.join(os.path.dirname(PASTA), "credenciais.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]  # o indicador só lê a planilha


def abrir_planilha():
    if os.path.exists(CREDENCIAIS_LOCAL):
        creds = Credentials.from_service_account_file(CREDENCIAIS_LOCAL, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=SCOPES)
    return gspread.authorize(creds).open_by_key(PLANILHA_ID)


def ler_resumo():
    """Aba do resumo: Data (datetime) + quantidades (int)."""
    valores = abrir_planilha().worksheet(ABA_RESUMO).get_all_values()
    if len(valores) < 2:
        return pd.DataFrame(columns=["Data", *COLUNAS_STATUS])

    df = pd.DataFrame(valores[1:], columns=valores[0])
    df["Data"] = pd.to_datetime(df["Data"], format="%d/%m/%Y")
    for col in COLUNAS_STATUS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    return df.sort_values("Data").reset_index(drop=True)


def ler_pedidos():
    """Aba de pedidos: colunas principais, com as datas como datetime."""
    valores = abrir_planilha().worksheet(ABA_PEDIDOS).get_all_values()
    colunas = ["Pedido", "Remessa", "data_picking", "meta_producao", "data_sm", "OTS"]
    if len(valores) < 2:
        return pd.DataFrame(columns=colunas)

    df = pd.DataFrame(valores[1:], columns=valores[0])[colunas]
    for col in ["data_picking", "meta_producao", "data_sm"]:
        df[col] = pd.to_datetime(df[col], format="%d/%m/%Y %H:%M:%S", errors="coerce")
    return df.sort_values("meta_producao").reset_index(drop=True)


# =========================
# APARÊNCIA
# =========================
MESES_ABREV = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
STATUS_GRAFICO = {"ots_sim": "OTS sim", "ots_nao": "OTS não", "em_aberto": "Em aberto"}
STATUS_GRAFICO_POR_CODIGO = {"OTS_SIM": "OTS sim", "OTS_NAO": "OTS não", "EM_ABERTO": "Em aberto"}  # status da aba de pedidos
# Semáforo: verde = deu certo, vermelho = falhou, amarelo = em andamento.
# As mesmas cores pintam as barras do gráfico e o percentual dos cards.
CORES = {"OTS sim": "#6DBB84", "OTS não": "#C62828", "Em aberto": "#ECC354"}
# Texto do percentual nos cards: branco no verde e no vermelho, escuro no amarelo (branco não seria lido)
TEXTO_PERCENTUAL = {"OTS sim": "#FFFFFF", "OTS não": "#FFFFFF", "Em aberto": "#5C4300"}
ALTURA_KPI = 140  # px, todos os cards iguais (com ou sem percentual embaixo)
IMAGEM_FAIXA = os.path.join(PASTA, "imagens", "mercado_livre.png")  # opcional: sem o arquivo, a faixa fica sem imagem
# A faixa usa o mesmo amarelo do fundo da imagem (#FFE700) para o logo se misturar com ela

st.set_page_config(layout="wide")

# Faixa amarela do topo: pinta o container com key="faixa" (o Streamlit dá a ele a classe st-key-faixa)
st.markdown(
    """
    <style>
    .st-key-faixa { background-color:#FFE700; padding:16px 24px; border-radius:6px; }
    .st-key-faixa h1 { margin:0; padding:0; color:#2D3277; font-size:2.2rem; }
    .st-key-faixa label p { color:#2D3277; font-weight:600; }
    .st-key-faixa .periodo-dados { color:#2D3277; font-size:0.95rem; }
    /* Item marcado e campo em foco no azul do logo, no lugar do vermelho padrão do Streamlit */
    .st-key-faixa label[data-baseweb="radio"]:has(input:checked) > div:first-child { background-color:#2D3277 !important; }
    .st-key-faixa [data-baseweb="select"] > div:focus-within { border-color:#2D3277 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Percentual dos cards na cor do status: cada card fica num container com key="kpi_<n>" (classe st-key-kpi_<n>)
CHAVE_KPI = {status: f"kpi_{i}" for i, status in enumerate(CORES)}
st.markdown(
    "<style>"
    + "".join(
        f".st-key-{CHAVE_KPI[s]} [data-testid='stMetricDelta'] {{ background-color:{CORES[s]}; color:{TEXTO_PERCENTUAL[s]}; font-weight:600; }}"
        f".st-key-{CHAVE_KPI[s]} [data-testid='stMetricDelta'] * {{ color:{TEXTO_PERCENTUAL[s]}; }}"
        for s in CORES
    )
    + "</style>",
    unsafe_allow_html=True,
)


# Guarda a leitura por 5 minutos para não ler o Sheets a cada clique.
# Quando a automação roda na tela principal, ela limpa essa memória e os dados novos aparecem na hora.
@st.cache_data(ttl=300, show_spinner="Lendo os dados no Google Sheets...")
def carregar_resumo():
    return ler_resumo()


@st.cache_data(ttl=300, show_spinner="Lendo os pedidos no Google Sheets...")
def carregar_pedidos():
    return ler_pedidos()


def pct_ots(sim, total):
    """% OTS = OTS sim sobre o total de pedidos (os em aberto contam no total)."""
    return sim / total if total else None


def nome_mes(periodo):
    return f"{MESES_ABREV[periodo.month - 1]}/{periodo.year}"


def numero(valor):
    return f"{int(valor):,}".replace(",", ".")


def pct_texto(valor):
    return f"{valor:.1%}".replace(".", ",")


# =========================
# LEITURA DOS DADOS
# =========================
resumo = carregar_resumo()
if resumo.empty:
    st.info(f"A aba '{ABA_RESUMO}' está vazia. Execute a automação na tela principal.")
    st.stop()

resumo["Mes"] = resumo["Data"].dt.to_period("M")
meses = sorted(resumo["Mes"].unique(), reverse=True)
anos = sorted(resumo["Data"].dt.year.unique(), reverse=True)

VISAO_DIA, VISAO_ANO = "Dia a dia", "Mensal"

# =========================
# FAIXA: IMAGEM + TÍTULO + VISÃO + FILTRO
# =========================
with st.container(key="faixa"):
    if os.path.exists(IMAGEM_FAIXA):
        col_imagem, col_titulo, col_visao, col_filtro = st.columns([2, 5, 2, 2], vertical_alignment="center")
        col_imagem.image(IMAGEM_FAIXA, width="stretch")
    else:
        col_titulo, col_visao, col_filtro = st.columns([6, 2, 2], vertical_alignment="center")
    col_titulo.markdown(
        f"""
        <div style="display:flex; align-items:baseline; gap:16px; flex-wrap:wrap;">
            <h1>Indicador SLA OTS E-commerce</h1>
            <span class="periodo-dados">Dados atualizados: {resumo['Data'].min():%d/%m/%Y} a {resumo['Data'].max():%d/%m/%Y}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    visao = col_visao.radio("Visão:", options=[VISAO_DIA, VISAO_ANO], horizontal=True)
    # O filtro acompanha a visão: mês no dia a dia, ano na visão mensal
    if visao == VISAO_DIA:
        mes = col_filtro.selectbox("Mês:", options=meses, format_func=nome_mes)
    else:
        ano = col_filtro.selectbox("Ano:", options=anos)

# =========================
# CARDS E GRÁFICO (usados no mês e no ano)
# =========================
def kpi(coluna, titulo, valor, percentual=None):
    """Card com o número e, embaixo, o percentual (sem seta). Nos cards de status, o percentual
    ganha a cor do status (CSS pela key do container); nos outros, fica cinza."""
    with coluna.container(key=CHAVE_KPI.get(titulo)):
        st.metric(
            titulo, valor, border=True, height=ALTURA_KPI,
            delta=percentual, delta_color="off", delta_arrow="off",
            delta_description="dos pedidos" if percentual else None,
        )


def mostrar_cards(df):
    """4 cards com os totais de `df`: Pedidos e cada status (com o % dos pedidos embaixo).
    O % do OTS sim é o % OTS do período."""
    totais = df[COLUNAS_STATUS].sum()

    def pct_dos_pedidos(qtde):
        return pct_texto(qtde / totais["ots_total"]) if totais["ots_total"] else None

    col1, col2, col3, col4 = st.columns(4)
    kpi(col1, "Pedidos", numero(totais["ots_total"]))
    kpi(col2, "OTS sim", numero(totais["ots_sim"]), pct_dos_pedidos(totais["ots_sim"]))
    kpi(col3, "OTS não", numero(totais["ots_nao"]), pct_dos_pedidos(totais["ots_nao"]))
    kpi(col4, "Em aberto", numero(totais["em_aberto"]), pct_dos_pedidos(totais["em_aberto"]))


def passo_redondo(valor):
    """Menor número "redondo" (1, 2, 2,5 ou 5 vezes uma potência de 10) maior ou igual a `valor`."""
    potencia = 10 ** max(len(str(int(max(valor, 1)))) - 1, 0)
    for fator in (1, 2, 2.5, 5, 10):
        if fator * potencia >= valor:
            return int(fator * potencia)


def grafico_barras_pct(tabela, nome_periodo):
    """Barras empilhadas por status (embaixo) + linha do % OTS (em cima), com rótulos.

    `tabela` tem uma linha por período (dia ou mês), na ordem do eixo, com a coluna "Periodo"
    (texto do eixo X), as colunas de status e a coluna "vencido" (True se o período já passou).
    Período vencido com pedido em aberto ganha o alerta "⚠ N em aberto" acima da barra.
    `nome_periodo` aparece na dica ao passar o mouse.
    """
    tabela = tabela.copy()
    tabela["pct_ots"] = [pct_ots(s, t) for s, t in zip(tabela["ots_sim"], tabela["ots_total"])]
    # Um rótulo por período (eixo por categoria): barras largas e sem rótulo repetido no eixo
    eixo_x = alt.X("Periodo:N", title=None, sort=tabela["Periodo"].tolist(), axis=alt.Axis(labelAngle=0))
    dica_periodo = alt.Tooltip("Periodo:N", title=nome_periodo)

    # Barras empilhadas montadas à mão (início e fim de cada parte), para o rótulo ficar no meio de cada parte.
    # De baixo pra cima: OTS sim, OTS não, Em aberto.
    partes = []
    for _, d in tabela.iterrows():
        inicio = 0
        for coluna, status in STATUS_GRAFICO.items():
            qtde = int(d[coluna])
            partes.append({"Periodo": d["Periodo"], "Status": status, "Pedidos": qtde, "inicio": inicio, "fim": inicio + qtde})
            inicio += qtde
    volume = pd.DataFrame(partes)
    volume["meio"] = (volume["inicio"] + volume["fim"]) / 2
    # Rótulos já como texto, com separador de milhar com ponto (1.234), como nos cards
    volume["rotulo"] = volume["Pedidos"].map(numero)
    tabela["rotulo_total"] = tabela["ots_total"].map(numero)

    # As barras ficam embaixo e a linha do % em cima, para os rótulos não se encontrarem.
    # Barra mais alta até ~62% da altura (o total e o alerta dela até ~68%); o 0% da linha fica em ~73%
    maior = max(int(tabela["ots_total"].max()), 1)
    escala_pedidos = alt.Scale(domain=[0, maior * 1.6])
    escala_pct = alt.Scale(domain=[-3.0, 1.12])

    # Eixo de pedidos com números redondos (0, 100, 200...), só até a barra mais alta
    passo = passo_redondo(maior / 4)
    barras = alt.Chart(volume).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, opacity=1).encode(
        x=eixo_x,
        y=alt.Y("inicio:Q", title="Pedidos", scale=escala_pedidos, axis=alt.Axis(values=list(range(0, maior + 1, passo)))),
        y2="fim:Q",
        color=alt.Color(
            "Status:N",
            scale=alt.Scale(domain=list(CORES), range=list(CORES.values())),
            legend=alt.Legend(orient="top", title=None),
        ),
        tooltip=[dica_periodo, "Status:N", "Pedidos:Q"],
    )

    # Quantidade dentro de cada parte (só nas partes altas o bastante para caber o número)
    rotulo_partes = (
        alt.Chart(volume[volume["Pedidos"] >= maior * 0.08])
        .mark_text(color="white", fontSize=11, fontWeight="bold")
        .encode(x=eixo_x, y=alt.Y("meio:Q", scale=escala_pedidos), text="rotulo:N")
    )

    # Total do período em cima da barra
    rotulo_total = (
        alt.Chart(tabela)
        .mark_text(dy=-8, color="#424242", fontSize=11, fontWeight="bold")
        .encode(x=eixo_x, y=alt.Y("ots_total:Q", scale=escala_pedidos), text="rotulo_total:N")
    )

    # Alerta acima do total: período que já passou e ainda tem pedido em aberto (meta vencida, não faturado).
    # Amarelo mais escuro que o da barra, para ser lido no fundo branco.
    vencidos = tabela[tabela["vencido"] & (tabela["em_aberto"] > 0)].copy()
    vencidos["alerta"] = "⚠ " + vencidos["em_aberto"].map(numero) + " em aberto"
    rotulo_alerta = (
        alt.Chart(vencidos)
        .mark_text(dy=-24, color="#B7891F", fontSize=11, fontWeight="bold")
        .encode(x=eixo_x, y=alt.Y("ots_total:Q", scale=escala_pedidos), text="alerta:N")
    )

    # % OTS do período, na metade de cima, com eixo próprio à direita
    base_pct = alt.Chart(tabela.dropna(subset=["pct_ots"])).encode(
        x=eixo_x,
        y=alt.Y(
            "pct_ots:Q", title="% OTS", scale=escala_pct,
            axis=alt.Axis(format="%", orient="right", values=[0, 0.25, 0.5, 0.75, 1]),
        ),
    )
    # Linha suave: "monotone" curva entre os pontos sem passar acima/abaixo dos valores reais
    linha_pct = base_pct.mark_line(
        point=alt.OverlayMarkDef(size=50), color="#1565C0", strokeWidth=2, interpolate="monotone"
    ).encode(
        tooltip=[dica_periodo, alt.Tooltip("pct_ots:Q", title="% OTS", format=".1%")]
    )
    rotulo_pct = base_pct.mark_text(dy=-12, color="#1565C0", fontSize=12, fontWeight="bold").encode(
        text=alt.Text("pct_ots:Q", format=".0%")
    )

    return (
        alt.layer(barras + rotulo_partes + rotulo_total + rotulo_alerta, linha_pct + rotulo_pct)
        .resolve_scale(y="independent")
        .properties(height=600)
    )


# =========================
# VISÃO MENSAL: CARDS DO ANO E GRÁFICO POR MÊS
# =========================
if visao == VISAO_ANO:
    do_ano = resumo[resumo["Data"].dt.year == ano]
    mostrar_cards(do_ano)

    st.subheader(f"Por mês: {ano}")
    mensal = do_ano.groupby("Mes")[COLUNAS_STATUS].sum().sort_index().reset_index()
    mensal["Periodo"] = [MESES_ABREV[p.month - 1] for p in mensal["Mes"]]
    mensal["vencido"] = mensal["Mes"] < pd.Timestamp.today().to_period("M")
    st.altair_chart(grafico_barras_pct(mensal, "Mês"), width="stretch")
    st.stop()

# =========================
# DIA A DIA: CARDS DO MÊS, GRÁFICO POR DIA E PEDIDOS
# =========================
selecao = resumo[resumo["Mes"] == mes]
mostrar_cards(selecao)

st.subheader(f"Por dia: {nome_mes(mes)}")
diario = selecao.assign(
    Periodo=selecao["Data"].dt.strftime("%d/%m"),
    vencido=selecao["Data"] < pd.Timestamp.today().normalize(),
)
st.altair_chart(grafico_barras_pct(diario, "Dia"), width="stretch")

# Pedidos do mês (aba dados_sla)
st.subheader(f"Pedidos: {nome_mes(mes)}")

pedidos = carregar_pedidos()
pedidos_mes = pedidos[pedidos["meta_producao"].dt.to_period("M") == mes]

if pedidos_mes.empty:
    st.info(f"A aba '{ABA_PEDIDOS}' não tem pedidos com Meta Produção em {nome_mes(mes)}.")
else:
    # Status com os mesmos nomes da legenda do gráfico (OTS_SIM -> OTS sim)
    tabela_pedidos = pedidos_mes.assign(OTS=pedidos_mes["OTS"].map(STATUS_GRAFICO_POR_CODIGO).fillna(pedidos_mes["OTS"]))
    formato_data_hora = "DD/MM/YYYY HH:mm"
    # Cabeçalhos com os mesmos nomes da aba de pedidos; só as datas ganham formato
    st.dataframe(
        tabela_pedidos,
        column_config={
            "data_picking": st.column_config.DatetimeColumn("data_picking", format=formato_data_hora),
            "meta_producao": st.column_config.DatetimeColumn("meta_producao", format=formato_data_hora),
            "data_sm": st.column_config.DatetimeColumn("data_sm", format=formato_data_hora),
        },
        hide_index=True,
        width="stretch",
    )

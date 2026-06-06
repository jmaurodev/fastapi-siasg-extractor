import asyncio
import math
import re

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
async def index():
    """Página de consulta para usuários de teste."""
    return FileResponse("static/index.html")

BASE_URL = "https://www2.comprasnet.gov.br"
PESQUISAR_LICITACAO_PATH = "/siasgnet-atasrp/public/pesquisarLicitacaoSRP.do"
PESQUISAR_ITEM_PATH = "/siasgnet-atasrp/public/pesquisarItemSRP.do"
VISUALIZAR_ITEM_PATH = "/siasgnet-atasrp/public/visualizarItemSRP.do"
ITENS_POR_PAGINA = 20
# Quantos detalhes de item buscar em paralelo.
DETALHE_CONCORRENCIA = 5

HTML_PARSER = "html.parser"
SELETOR_LINHAS = "tbody tr"

# selecionarLicitacao('uasg','mod','num','ano', PK) — captura a modalidade.
SELECIONAR_LICITACAO_RE = re.compile(
    r"selecionarLicitacao\(\s*'\d+'\s*,\s*'(?P<modalidade>\d+)'\s*,\s*"
    r"'\d+'\s*,\s*'\d+'\s*,\s*\d+\s*\)"
)
# selecionarItem(PK) — PK do item (codigoItemAtaSRP).
SELECIONAR_ITEM_RE = re.compile(r"selecionarItem\(\s*(\d+)\s*\)")
# "128 registros encontrados, exibindo do 1º ao 20º."
TOTAL_REGISTROS_RE = re.compile(r"(\d+)\s+registros?\s+encontrados", re.IGNORECASE)


@app.get("/pregao/itens")
async def get_pregao_itens(uasg: str, numero: str, ano: str):
    """Todos os itens do pregão, com seus campos descritivos.

    Deriva a modalidade a partir da pesquisa de licitação, coleta os itens
    (paginados) e visita o detalhe de cada um para obter a descrição detalhada.
    """
    async with _novo_client() as client:
        modalidade = await _obter_modalidade(client, uasg, ano, numero)
        itens = await _coletar_itens(client, uasg, modalidade, numero, ano)
        pks = [item["pk"] for item in itens if item["pk"] is not None]

        semaforo = asyncio.Semaphore(DETALHE_CONCORRENCIA)

        async def carregar(pk: int) -> dict:
            async with semaforo:
                resp = await client.get(
                    VISUALIZAR_ITEM_PATH,
                    params={"method": "iniciar", "itemAtaSRP.codigoItemAtaSRP": pk},
                )
                resp.raise_for_status()
                return _parse_item_pregao(resp.text)

        detalhados = await asyncio.gather(*(carregar(pk) for pk in pks))

    if not detalhados:
        raise HTTPException(status_code=404, detail="Nenhum item encontrado.")
    return {"total": len(detalhados), "itens": detalhados}


def _novo_client() -> httpx.AsyncClient:
    # verify=False: o comprasnet serve cadeia ICP-Brasil incompleta e a
    # verificação padrão falha. TODO: apontar verify= para o bundle ICP-Brasil.
    return httpx.AsyncClient(
        base_url=BASE_URL, follow_redirects=True, timeout=30.0, verify=False
    )


def _sopa(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, HTML_PARSER)


async def _obter_modalidade(
    client: httpx.AsyncClient, uasg: str, ano: str, numero: str
) -> str:
    """Pesquisa a licitação e devolve o código da modalidade de compra."""
    await client.get(PESQUISAR_LICITACAO_PATH, params={"method": "iniciar"})
    resp = await client.post(
        PESQUISAR_LICITACAO_PATH,
        data={
            "method": "pesquisar",
            "casoDeUsoOrigem": "",
            "funcaoRetorno": "",
            "parametro.uasg.numeroUasg": uasg,
            "parametro.uasg.nome": "",
            "parametro.numeroLicitacao": numero,
            "parametro.anoLicitacao": ano,
        },
    )
    resp.raise_for_status()

    soup = _sopa(resp.text)
    tabela = soup.find("table", id="licitacao")
    link = tabela.find("a", href=True) if tabela else None
    m = SELECIONAR_LICITACAO_RE.search(link["href"]) if link else None
    if m is None:
        raise HTTPException(status_code=404, detail="Licitação não encontrada.")
    return m.group("modalidade")


async def _coletar_itens(
    client: httpx.AsyncClient, uasg: str, modalidade: str, numero: str, ano: str
) -> list[dict]:
    identificacao = {
        "parametro.identificacaoCompra.numeroUasg": uasg,
        "parametro.identificacaoCompra.modalidadeCompra": modalidade,
        "parametro.identificacaoCompra.numeroCompra": numero,
        "parametro.identificacaoCompra.anoCompra": ano,
    }

    # Página 1: method=iniciar já traz os itens e o total de registros.
    resp = await client.get(
        PESQUISAR_ITEM_PATH, params={**identificacao, "method": "iniciar"}
    )
    resp.raise_for_status()
    itens = _parse_itens(resp.text)
    total = _parse_total(resp.text)

    # Páginas seguintes: method=consultarPorFiltro&numeroPagina=N.
    n_paginas = math.ceil(total / ITENS_POR_PAGINA) if total else 1
    for pagina in range(2, n_paginas + 1):
        resp = await client.get(
            PESQUISAR_ITEM_PATH,
            params={
                **identificacao,
                "method": "consultarPorFiltro",
                "numeroPagina": pagina,
            },
        )
        resp.raise_for_status()
        itens.extend(_parse_itens(resp.text))

    return itens


def _parse_itens(html: str) -> list[dict]:
    soup = _sopa(html)
    tabela = soup.find("table", id="item")
    if tabela is None:
        return []

    itens = []
    for tr in tabela.select(SELETOR_LINHAS):
        tds = tr.find_all("td")
        if len(tds) < 6:
            continue
        link = tds[5].find("a", href=True)
        m = SELECIONAR_ITEM_RE.search(link["href"]) if link else None
        itens.append({"pk": int(m.group(1)) if m else None})
    return itens


def _parse_total(html: str) -> int:
    m = TOTAL_REGISTROS_RE.search(html)
    return int(m.group(1)) if m else 0


def _parse_item_pregao(html: str) -> dict:
    """Extrai os campos descritivos de um item da página de detalhe."""
    soup = _sopa(html)

    def campo_input(name: str) -> str | None:
        el = soup.find("input", attrs={"name": name})
        return el.get("value", "").strip() if el else None

    def campo_textarea(name: str) -> str | None:
        el = soup.find("textarea", attrs={"name": name})
        return el.get_text().strip() if el else None

    # "445484 - Água Mineral Natural" -> categoria "445484", item "Água Mineral Natural"
    descricao = campo_input("cabecalhoItemSRP.descricaoItem") or ""
    categoria, separador, item = descricao.partition(" - ")
    if not separador:  # sem " - ": tudo é o nome do item, sem categoria
        categoria, item = "", descricao

    return {
        "numero_item": campo_input("cabecalhoItemSRP.numeroItem"),
        "tipo_item": campo_input("cabecalhoItemSRP.tipoItem"),
        "categoria": categoria.strip() or None,
        "item": item.strip() or None,
        "descricao_detalhada": campo_textarea(
            "cabecalhoItemSRP.descricaoDetalhadaItem"
        ),
        "unidade_fornecimento": campo_input("cabecalhoItemSRP.unidadeFornecimento"),
    }

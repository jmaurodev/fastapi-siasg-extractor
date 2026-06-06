# fastapi-siasg-extractor

Extrator de itens de pregão SRP do **SIASGnet-ATASRP** (comprasnet), com API em
FastAPI e uma interface web simples para usuários de teste.

A partir de **UASG**, **número** e **ano** do pregão, o serviço navega pelo fluxo
público do comprasnet (pesquisa de licitação → itens → detalhe de cada item) e
devolve todos os itens com seus campos descritivos.

## Requisitos

- Python >= 3.14
- [uv](https://docs.astral.sh/uv/)

## Instalação

```bash
uv sync
```

## Executando

```bash
uv run uvicorn main:app --reload
```

- Interface de teste: <http://127.0.0.1:8000/>
- Documentação dos devs (Swagger): <http://127.0.0.1:8000/docs>

## API

### `GET /pregao/itens`

Parâmetros (query): `uasg`, `numero`, `ano`.

```bash
curl "http://127.0.0.1:8000/pregao/itens?uasg=160298&numero=90019&ano=2025"
```

Resposta:

```json
{
  "total": 128,
  "itens": [
    {
      "numero_item": "1",
      "tipo_item": "Material",
      "categoria": "445484",
      "item": "Água Mineral Natural",
      "descricao_detalhada": "Água Mineral Natural Tipo Embalagem: Descartável ...",
      "unidade_fornecimento": "Copo 200,00 ML"
    }
  ]
}
```

A modalidade é derivada automaticamente da pesquisa de licitação. Como a
descrição detalhada só existe na página de detalhe, o serviço visita o detalhe
de cada item (com concorrência limitada por `DETALHE_CONCORRENCIA`), então a
consulta leva alguns segundos para pregões com muitos itens.

## Interface web

A página em `/` permite consultar, filtrar os resultados e exportar em **TXT**,
**CSV** (com BOM, pronto para Excel pt-BR) ou **JSON**.

## Observações

- TLS: o comprasnet serve cadeia ICP-Brasil incompleta, então o cliente HTTP usa
  `verify=False`. Para endurecer, aponte `verify=` para um bundle ICP-Brasil.
- Os arquivos `*.do` na raiz são capturas de HTML usadas durante o
  desenvolvimento e não são versionados (ver `.gitignore`).

# Rodar sem o Docker e testes

Para mexer no código, dá para rodar cada parte direto na máquina, sem esperar o agendamento do Airflow.

## Ambiente Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Extração e transformação

Os scripts rodam sozinhos com o período fixo definido em `PARAMS` no `src/extract.py` (hoje, 01/10/2026 a 02/10/2026, Pregão Eletrônico):

```bash
python -m src.extract      # gera data/raw/contratacoes_20261001_20261002_m6.json
python -m src.transform    # gera data/processed/contratacoes.csv
```

Para outro período, troque `PARAMS["dataInicial"]` e `PARAMS["dataFinal"]` (formato `AAAAMMDD`). A carga no banco não tem um script próprio: ela roda só pela DAG.

## Testes

```bash
make test      # ou só pytest
```

Os testes não fazem requisições reais: a API do PNCP e o servidor de e-mail são simulados. Eles cobrem:

- a paginação, as novas tentativas após `429` e o tratamento do `204` na extração;
- a limpeza dos textos, a conversão das datas, a remoção de duplicatas e o link para o edital na transformação;
- a carga e a atualização de registros no banco;
- as consultas e os indicadores do dashboard;
- a validação do `alertas.yml`, os filtros, o e-mail e o anexo dos alertas.

Os testes de banco usam um **PostgreSQL de verdade**, o banco `pncp_teste`, porque a atualização de registros depende do comportamento do Postgres. Com o Docker Compose no ar, eles se conectam em `localhost:5433` sozinhos. Sem o banco, esses testes aparecem como pulados (*skipped*) e os outros rodam normalmente.

Para usar outro banco de testes:

```bash
PNCP_TESTE_DB_URL=postgresql://usuario:senha@host:5432/pncp_teste pytest
```

> **Não aponte para o banco `pncp`.** Cada teste apaga e recria a tabela `contratacoes`.

## Dashboard

```bash
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

Rode da pasta raiz do projeto. Sem configurar nada, ele lê o banco `pncp` em `localhost:5433`, o mesmo do Docker Compose. Para outro banco, defina `PNCP_DB_URL`.

O endereço é **http://localhost:8501**, o mesmo do container: pare o serviço `dashboard` antes (`docker compose stop dashboard`) ou passe `--server.port 8502`.

## Documentação

Este site é feito com [MkDocs](https://www.mkdocs.org/) e o tema [Material](https://squidfunk.github.io/mkdocs-material/). As páginas ficam em `docs/` e o menu, no `mkdocs.yml`.

```bash
make docs
```

O `make docs` usa a imagem Docker do tema, na mesma versão do `requirements-docs.txt`, sem instalar nada na máquina. O site abre em **http://localhost:8000** e recarrega a cada página salva. `Ctrl+C` para.

Sem o Docker:

```bash
pip install -r requirements-docs.txt
mkdocs serve
``` A cada push na `main` que mexa em `docs/` ou no `mkdocs.yml`, o workflow `.github/workflows/docs.yml` publica a nova versão no GitHub Pages.

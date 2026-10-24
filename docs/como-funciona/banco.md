# Banco de dados

O Docker Compose sobe um único **PostgreSQL 16**, com três bancos:

| Banco | Para quê |
|---|---|
| `airflow` | Banco interno do Airflow: execuções, tarefas, usuários, conexões |
| `pncp` | Os dados do pipeline, lidos pelo dashboard e pelos alertas |
| `pncp_teste` | Usado só pelo `pytest`, que apaga e recria a tabela a cada teste |

Os bancos `pncp` e `pncp_teste` são criados pelo script `docker/postgres-init/01-banco-pncp.sql`. O Postgres só roda esse script quando o volume é criado pela primeira vez.

As tarefas acessam o banco `pncp` pela conexão `pncp_db`, definida no `docker-compose.yaml` pela variável `AIRFLOW_CONN_PNCP_DB`. Ela não aparece na tela de conexões do Airflow, mas funciona normalmente.

## A tabela `contratacoes`

A primeira carga cria a tabela e os índices (`CREATE TABLE IF NOT EXISTS`, em `src/load.py`). Antes disso, o banco `pncp` está vazio.

| Coluna | Tipo | Descrição |
|---|---|---|
| `numero_controle_pncp` | `TEXT`, **chave primária** | Identificador único da contratação no PNCP |
| `orgao` | `TEXT` | Órgão ou entidade responsável |
| `uf` | `CHAR(2)` | Sigla do estado |
| `municipio` | `TEXT` | Município da unidade compradora |
| `objeto` | `TEXT` | O que está sendo contratado |
| `modalidade` | `TEXT` | Nome da modalidade, como `Pregão - Eletrônico` |
| `data_publicacao` | `TIMESTAMP` | Data e hora da publicação no PNCP |
| `data_encerramento` | `TIMESTAMP` | Prazo final para envio de propostas |
| `valor_estimado` | `NUMERIC(18, 2)` | Valor total estimado, em reais. `0` indica orçamento sigiloso |
| `valor_homologado` | `NUMERIC(18, 2)` | Valor total homologado, quando já houver |
| `situacao` | `TEXT` | Situação da compra, como `Divulgada no PNCP` |
| `ano_compra` | `INTEGER` | Ano da compra |
| `link_pncp` | `TEXT` | Link para a página do edital no portal do PNCP |
| `atualizado_em` | `TIMESTAMP` | Quando a linha foi gravada ou atualizada pela última vez |

## Carga sem duplicatas

A carga faz um *upsert*: grava as contratações novas e, quando o `numero_controle_pncp` já existe, **atualiza a linha** com os dados mais recentes.

Por isso, processar o mesmo dia duas vezes não duplica nada. Também serve para atualizar a situação e o valor homologado de contratações antigas: basta reprocessar os dias delas (veja [Reprocessar dias que já rodaram](../instalacao/carregar-dias-anteriores.md#reprocessar-dias-que-já-rodaram)).

Campos vazios no CSV viram `NULL` no banco.

## Índices

| Índice | Coluna | Usado por |
|---|---|---|
| chave primária | `numero_controle_pncp` | O *upsert* da carga |
| `idx_contratacoes_data_publicacao` | `data_publicacao` | Os alertas (contratações do dia) e o período do dashboard |
| `idx_contratacoes_uf` | `uf` | O filtro de UF do dashboard |

## Consultar os dados

Pelo terminal:

```bash
docker compose exec postgres psql -U airflow -d pncp
```

Ou por qualquer cliente de PostgreSQL (DBeaver, pgAdmin, a extensão do VS Code) em `localhost:5433`, banco `pncp`, usuário `airflow` e senha `airflow`.

### Contratações por dia

```sql
SELECT data_publicacao::date AS dia, count(*)
FROM contratacoes
GROUP BY 1
ORDER BY 1 DESC
LIMIT 5;
```

```
    dia     | count
------------+-------
 2026-10-23 |  1585
 2026-10-22 |  1831
 2026-10-21 |  1629
 2026-10-20 |  1606
 2026-10-19 |  1514
```

### As maiores de um dia

```sql
SELECT numero_controle_pncp, uf, municipio, objeto, valor_estimado, data_encerramento
FROM contratacoes
WHERE data_publicacao >= '2026-10-22' AND data_publicacao < '2026-10-23'
ORDER BY valor_estimado DESC
LIMIT 3;
```

```
     numero_controle_pncp     | uf |  municipio   |              objeto               | valor_estimado |  data_encerramento
------------------------------+----+--------------+-----------------------------------+----------------+---------------------
 12264628000183-1-000061/2026 | AL | Campo Alegre | AQUISIÇÃO DE COMBUSTÍVEL          |    19901040.21 | 2026-11-10 09:00:00
 46634200000105-1-000080/2026 | SP | Itaí         | REGISTRO DE PREÇOS - MEDICAMENTOS |    13072907.10 | 2026-11-09 08:30:00
 05816630000152-1-008006/2026 | BA | Salvador     | Aquisição de bens comuns          |     9162032.00 | 2026-11-17 10:00:00
```

Comparar `data_publicacao` com um intervalo, em vez de usar `data_publicacao::date = '2026-10-22'`, deixa o Postgres usar o índice da coluna.

### Ainda abertas numa UF

```sql
SELECT orgao, municipio, objeto, valor_estimado, data_encerramento, link_pncp
FROM contratacoes
WHERE uf = 'DF' AND data_encerramento >= current_date
ORDER BY data_encerramento;
```

### Quanto tem valor sigiloso

```sql
SELECT round(100.0 * count(*) FILTER (WHERE valor_estimado = 0) / count(*), 1) AS pct_sigiloso
FROM contratacoes;
```

Cerca de 1 em cada 6 contratações tem o valor estimado zerado. Por isso o dashboard e os alertas tratam o zero como "sigiloso", e não como "de graça".

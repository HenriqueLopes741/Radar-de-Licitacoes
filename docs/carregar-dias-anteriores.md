# Carregar dias anteriores (backfill)

A DAG `pncp_pipeline` roda com `catchup=False`: ao ser ativada, ela só processa os dias a partir dali. Quem acabou de instalar o projeto começa com o banco vazio. Para trazer o histórico, use o **backfill** do Airflow, que cria uma execução para cada dia de um período.

Cada execução cobre um dia inteiro, no horário de Brasília. Por isso **a data pedida é o dia processado**: o backfill de 01/10 carrega as contratações publicadas em 01/10. O backfill também aceita datas anteriores ao `start_date` da DAG (13/10/2026).

> **Sugestão:** para começar, carregue os **últimos 30 dias**. É histórico suficiente para o dashboard e leva cerca de 1h30 só com o Pregão Eletrônico.

## Quanto tempo leva

Cerca de **3 minutos por dia e por modalidade**. A API do PNCP limita o número de requisições, e por isso a extração consulta uma modalidade de cada vez, mesmo com várias execuções em paralelo.

| Período | 1 modalidade | 3 modalidades |
|---|---|---|
| 7 dias | ~20 min | ~1 h |
| 30 dias | ~1h30 | ~4h30 |
| 90 dias | ~4h30 | ~13h30 |

Fins de semana e feriados têm poucas publicações e terminam mais rápido.

## Pela tela do Airflow

1. Em **http://localhost:8080**, abra a DAG `pncp_pipeline` e clique em **Acionar** (*Trigger*).
2. Troque de **Execução única** (*Single Run*) para **Backfill**.
3. Escolha o período: a data inicial e a final entram no backfill.
4. Em **Comportamento de reprocessamento** (*Reprocess Behaviour*), escolha:
   - **Execuções ausentes** (*Missing Runs*) para carregar só os dias que nunca rodaram;
   - **Todas as execuções** (*All Runs*) para rodar de novo os dias que já rodaram (veja [Reprocessar dias que já rodaram](#reprocessar-dias-que-já-rodaram)).
5. Em **Modalidades**, informe os códigos desejados (veja [Escolher as modalidades](#escolher-as-modalidades)).
6. **Deixe o campo Data vazio.** Se ele estiver preenchido, todas as execuções do backfill processam esse mesmo dia.
7. Confira quantas execuções a tela diz que vão ser criadas (uma por dia do período) e confirme.

As execuções aparecem na grade da DAG com o prefixo `backfill__`.

## Pela linha de comando

Os comandos rodam dentro de um container do Airflow:

```bash
docker compose exec airflow-scheduler airflow backfill create \
  --dag-id pncp_pipeline \
  --from-date 2026-10-01T00:00:00-03:00 \
  --to-date 2026-10-10T00:00:00-03:00
```

Esse comando carrega de 01/10 a 10/10, com os dois dias incluídos.

> **Informe as datas com o horário e o fuso (`T00:00:00-03:00`).** Só com a data (`--to-date 2026-10-10`), o Airflow considera meia-noite em UTC, que é 21h do dia anterior em Brasília, e **o último dia fica de fora**.

Para ver quais dias seriam processados sem criar nada, acrescente `--dry-run`. A lista mostra a data lógica de cada execução em UTC: `2026-10-01 03:00:00+00:00` é meia-noite de 01/10 em Brasília.

Para acompanhar o andamento:

```bash
docker compose exec airflow-scheduler airflow dags list-runs pncp_pipeline
```

### Escolher as modalidades

Sem nada informado, o backfill usa o padrão da DAG: só a modalidade **6 (Pregão Eletrônico)**. Para outras, passe a lista em `--dag-run-conf`:

```bash
docker compose exec airflow-scheduler airflow backfill create \
  --dag-id pncp_pipeline \
  --from-date 2026-10-01T00:00:00-03:00 \
  --to-date 2026-10-10T00:00:00-03:00 \
  --dag-run-conf '{"modalidades": [6, 8, 9]}'
```

Códigos mais comuns:

| Código | Modalidade |
|---|---|
| 4 | Concorrência Eletrônica |
| 6 | Pregão Eletrônico |
| 8 | Dispensa de Licitação |
| 9 | Inexigibilidade |

A lista completa está no [manual da API de consulta do PNCP](https://www.gov.br/pncp/pt-br/central-de-conteudo/manuais).

Cada modalidade a mais soma cerca de 3 minutos por dia ao tempo total.

### Reprocessar dias que já rodaram

Por padrão, o backfill **pula os dias que já têm execução**, mesmo que essa execução tenha falhado ou não tenha gravado nada no banco. Para rodar esses dias de novo, use `--reprocess-behavior`:

| Valor | O que faz |
|---|---|
| `none` (padrão) | Só cria execuções para os dias que nunca rodaram |
| `failed` | Também roda de novo os dias cuja execução falhou |
| `completed` | Roda de novo todos os dias do período |

```bash
docker compose exec airflow-scheduler airflow backfill create \
  --dag-id pncp_pipeline \
  --from-date 2026-10-01T00:00:00-03:00 \
  --to-date 2026-10-10T00:00:00-03:00 \
  --reprocess-behavior completed
```

Reprocessar não duplica registros: a carga usa o `numero_controle_pncp` como chave e atualiza as contratações que já estão no banco. Isso também serve para atualizar a situação e os valores homologados de contratações publicadas há mais tempo.

## Conferir o resultado

Para ver quantas contratações cada dia tem no banco:

```bash
docker compose exec postgres psql -U airflow -d pncp -c \
  "SELECT data_publicacao::date AS dia, count(*) FROM contratacoes GROUP BY 1 ORDER BY 1"
```

Os dados ficam no volume do Postgres e continuam lá depois de um `docker compose down`. Só o `docker compose down -v` apaga tudo.

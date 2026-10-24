# Parâmetros da DAG

Ao acionar a DAG à mão, o Airflow mostra um formulário com dois campos. A execução agendada da meia-noite usa sempre os valores padrão.

| Campo | Padrão | O que faz |
|---|---|---|
| **Modalidades** | `[6]` | Lista de códigos de modalidade a coletar. Precisa ter pelo menos um |
| **Data** | vazio | Dia a processar. Vazio: o dia anterior (veja [Agendamento](../como-funciona/agendamento.md)) |

## Pela tela do Airflow

1. Abra a DAG `pncp_pipeline` e clique em **Acionar** (*Trigger*).
2. Em **Modalidades**, informe os códigos desejados (tabela abaixo).
3. Em **Data**, escolha o dia no calendário ou deixe vazio.
4. Confirme.

Cada modalidade vira uma cópia do grupo de tarefas, com os seus próprios arquivos (veja [Fluxo da DAG](../como-funciona/fluxo.md#uma-cópia-por-modalidade)). Como as extrações rodam uma de cada vez, cada modalidade a mais soma cerca de 3 minutos.

## Pela linha de comando

```bash
docker compose exec airflow-scheduler airflow dags trigger pncp_pipeline \
  --conf '{"modalidades": [6, 8], "data": "2026-10-20"}'
```

Para vários dias seguidos, use o backfill: [Carregar dias anteriores](../instalacao/carregar-dias-anteriores.md).

## Modalidades

Códigos da tabela de domínio *Modalidade de Contratação* do [manual da API de consulta do PNCP](https://www.gov.br/pncp/pt-br/central-de-conteudo/manuais):

| Código | Modalidade |
|---|---|
| 1 | Leilão - Eletrônico |
| 2 | Diálogo Competitivo |
| 3 | Concurso |
| 4 | Concorrência - Eletrônica |
| 5 | Concorrência - Presencial |
| 6 | Pregão - Eletrônico |
| 7 | Pregão - Presencial |
| 8 | Dispensa de Licitação |
| 9 | Inexigibilidade |
| 10 | Manifestação de Interesse |
| 11 | Pré-qualificação |
| 12 | Credenciamento |
| 13 | Leilão - Presencial |

O padrão é o Pregão Eletrônico, a modalidade usada na compra de bens e serviços comuns.

## Outros ajustes no código

| O que mudar | Onde |
|---|---|
| Modalidades padrão | `Param([6], ...)` em `dags/pncp_pipeline.py` |
| Horário de execução | `schedule` em `dags/pncp_pipeline.py` |
| Novas tentativas das tarefas | `default_args` em `dags/pncp_pipeline.py` |
| Pausa entre páginas e tentativas após `429` | `PAUSA_ENTRE_PAGINAS`, `ESPERA_APOS_429` e `MAX_TENTATIVAS` em `src/extract.py` |
| Período usado ao rodar sem o Airflow | `PARAMS["dataInicial"]` e `PARAMS["dataFinal"]` em `src/extract.py` |
| Campos do CSV | dicionário `colunas` em `src/transform.py` |
| Colunas gravadas no banco | `COLUNAS` e `CRIAR_TABELA` em `src/load.py` |
| Quantas contratações aparecem no corpo do e-mail | `LIMITE_NO_EMAIL` em `src/alertas.py` |

> **Ao mudar os campos do CSV,** mude também `COLUNAS` e `CRIAR_TABELA` em `src/load.py`. A carga lê exatamente as colunas de `COLUNAS`, e o `CREATE TABLE IF NOT EXISTS` não altera uma tabela que já existe: uma coluna nova precisa de um `ALTER TABLE` no banco.

# Agendamento

**Cada execução da DAG cobre um dia inteiro**, de 00:00 a 23:59:59 no horário de Brasília. Ela só pode rodar quando esse dia acaba, por isso dispara à meia-noite seguinte.

| Execução | Quando roda | Dia processado |
|---|---|---|
| Agendada | 00:00 de 24/10 | 23/10 |
| Ao ativar a DAG pela primeira vez, às 15h de 24/10 | Na hora | 23/10, o último dia completo |
| Acionada à mão, com o campo **Data** vazio | Na hora | O dia anterior |
| Acionada à mão, com **Data** = 20/10/2026 | Na hora | 20/10 |
| Backfill de 01/10 a 10/10 | Na hora, uma execução por dia | Cada dia de 01/10 a 10/10 |

Em resumo: **para escolher o dia, use o campo Data** ao acionar a DAG, ou um backfill para vários dias. Não é preciso mexer na data lógica.

## Como o dia é calculado

A DAG usa um `CronDataIntervalTimetable` com `0 0 * * *` no fuso `America/Sao_Paulo`. Para o Airflow, cada execução tem um **intervalo de dados** (*data interval*): a de 23/10 vai de `23/10 00:00` a `24/10 00:00`.

A função `dia_a_processar`, em `src/extract.py`, escolhe o dia assim:

1. Se o parâmetro **Data** foi preenchido, usa essa data.
2. Senão, usa o **início do intervalo**, convertido para o horário de Brasília.

A conversão importa porque o Airflow guarda os horários em UTC: meia-noite de 23/10 em Brasília é `2026-10-23 03:00 UTC`.

No backfill, a **data lógica** de cada execução é o início do intervalo. Por isso a data pedida no backfill é o próprio dia processado.

## Início e execuções perdidas

- `start_date` é **13/10/2026**: a DAG não agenda nada antes disso. O backfill, por outro lado, aceita qualquer data.
- `catchup=False`: ao ser ativada, ou depois de ficar parada uns dias, a DAG não tenta recuperar todos os dias perdidos. Ela roda só o último dia completo. Para preencher os buracos, use o [backfill](../instalacao/carregar-dias-anteriores.md).

## Mudar o horário

O horário fica no `schedule` em `dags/pncp_pipeline.py`. Para rodar às 6h, por exemplo:

```python
schedule=CronDataIntervalTimetable("0 6 * * *", timezone=FUSO),
```

A extração continua pedindo à API o **dia** em que o intervalo começa. Assim, a execução das 6h de 24/10 ainda processa 23/10: o efeito é só buscar os dados 6 horas mais tarde.

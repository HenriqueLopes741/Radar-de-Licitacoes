# API do PNCP

A extração usa o endpoint público [`/v1/contratacoes/publicacao`](https://pncp.gov.br/api/consulta/swagger-ui/index.html) da API de consulta do PNCP. Ele não pede cadastro nem chave de acesso.

```
GET https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao
```

| Parâmetro | Valor enviado |
|---|---|
| `dataInicial` e `dataFinal` | O dia processado, no formato `AAAAMMDD` (os dois iguais) |
| `codigoModalidadeContratacao` | A modalidade da cópia do grupo (veja [Parâmetros da DAG](../funcoes/parametros.md#modalidades)) |
| `pagina` | De 1 até a última página |
| `tamanhoPagina` | 50, o máximo aceito |

A resposta traz as contratações em `data` e o total de páginas em `totalPaginas`. Um dia típico de Pregão Eletrônico tem cerca de 1.600 contratações, ou 32 páginas.

## Paginação

A extração pede a página 1, lê o `totalPaginas` e segue até a última. No fim, junta tudo num único JSON. Ela também para antes se uma página vier sem registros.

## Limite de requisições

A API aceita cerca de **8 requisições a cada 45 segundos**. Acima disso, responde `429 Too Many Requests`. Para não chegar lá:

- há uma **pausa de 6 segundos** entre as páginas (`PAUSA_ENTRE_PAGINAS` em `src/extract.py`);
- só **uma extração roda por vez**, mesmo com várias modalidades ou vários dias de backfill em paralelo.

Se mesmo assim vier um `429`, a extração espera o tempo indicado no cabeçalho `Retry-After` (ou 30 segundos, se ele não vier) e pede a mesma página de novo, **até 5 vezes**.

As pausas explicam o tempo de cada extração: 32 páginas × 6 segundos dão cerca de **3 minutos por dia e por modalidade**.

## Respostas da API

| Resposta | O que a extração faz |
|---|---|
| `200` | Guarda os registros e segue para a próxima página |
| `204` (sem corpo) | Não há contratações no dia: grava uma lista vazia |
| `429` | Espera e tenta a mesma página de novo, até 5 vezes |
| Outro erro (`400`, `500`...) | Mostra a resposta no log e falha na hora |

Quando a extração falha, o Airflow tenta a tarefa inteira de novo depois de 5 minutos, até 3 vezes (veja [Novas tentativas](fluxo.md#novas-tentativas)). Cada requisição tem um limite de 60 segundos para responder.

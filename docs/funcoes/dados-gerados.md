# Dados gerados

Cada dia processado gera dois arquivos por modalidade, na pasta `data/` do projeto, e as mesmas linhas no banco `pncp`.

| Arquivo | Conteúdo |
|---|---|
| `data/raw/contratacoes_20261022_m6.json` | O retorno da API, sem tratamento, com todas as páginas juntas |
| `data/processed/contratacoes_20261022_m6.csv` | As contratações tratadas, uma por linha |

O nome tem o dia (`AAAAMMDD`) e a modalidade (`m6` = Pregão Eletrônico). Assim, cada modalidade tem os seus arquivos, e um dia novo não sobrescreve os anteriores. Processar o mesmo dia de novo sobrescreve os arquivos dele.

A pasta `data/` fica fora do Git.

## O que a transformação faz

- Achata o JSON aninhado: `orgaoEntidade.razaoSocial` vira `orgao`, `unidadeOrgao.ufSigla` vira `uf`, e assim por diante.
- Mantém só os campos da tabela abaixo, com nomes em português.
- Remove espaços repetidos e quebras de linha dos textos.
- Converte as datas. Uma data inválida fica vazia, em vez de quebrar a carga.
- Remove registros sem `numero_controle_pncp` e contratações repetidas, mantendo a primeira.
- Monta o link para a página do edital a partir do `numero_controle_pncp`.

## Colunas

| Coluna | Campo na API | Descrição |
|---|---|---|
| `numero_controle_pncp` | `numeroControlePNCP` | Identificador único da contratação no PNCP |
| `orgao` | `orgaoEntidade.razaoSocial` | Órgão ou entidade responsável |
| `uf` | `unidadeOrgao.ufSigla` | Sigla do estado |
| `municipio` | `unidadeOrgao.municipioNome` | Município da unidade compradora |
| `objeto` | `objetoCompra` | O que está sendo contratado |
| `modalidade` | `modalidadeNome` | Nome da modalidade |
| `data_publicacao` | `dataPublicacaoPncp` | Data e hora da publicação no PNCP |
| `data_encerramento` | `dataEncerramentoProposta` | Prazo final para envio de propostas |
| `valor_estimado` | `valorTotalEstimado` | Valor total estimado, em reais. `0` indica orçamento sigiloso |
| `valor_homologado` | `valorTotalHomologado` | Valor total homologado, quando já houver |
| `situacao` | `situacaoCompraNome` | Situação da compra |
| `ano_compra` | `anoCompra` | Ano da compra |
| `link_pncp` | calculado | Link para a página do edital no portal do PNCP |

## O link do edital

O `numero_controle_pncp` tem o CNPJ do órgão, o número sequencial da compra e o ano. O link junta essas partes no endereço do portal:

```
00509968000148-1-003623/2026  →  https://pncp.gov.br/app/editais/00509968000148/2026/3623
```

Um número fora desse padrão fica sem link, em vez de ganhar um link errado.

## Exemplo do CSV

Três linhas de `contratacoes_20261022_m6.csv`:

```csv
numero_controle_pncp,orgao,uf,municipio,objeto,modalidade,data_publicacao,data_encerramento,valor_estimado,valor_homologado,situacao,ano_compra,link_pncp
60453032000174-1-000279/2026,UNIVERSIDADE FEDERAL DE SAO PAULO,SP,São Paulo,Aquisição de livros impressos para o Campus São Paulo,Pregão - Eletrônico,2026-10-22 04:00:06,2026-11-05 10:00:00,63241.69,,Divulgada no PNCP,2026,https://pncp.gov.br/app/editais/60453032000174/2026/279
00444232000139-1-001371/2026,INDUSTRIA DE MATERIAL BELICO DO BRASIL IMBEL,MG,Juiz de Fora,Monitoramento de Emissões Atmosféricas da Caldeira a Óleo,Pregão - Eletrônico,2026-10-22 04:00:08,2026-11-16 09:00:00,52908.16,,Divulgada no PNCP,2026,https://pncp.gov.br/app/editais/00444232000139/2026/1371
00509968000148-1-003623/2026,TRIBUNAL SUPERIOR DO TRABALHO,RJ,Rio de Janeiro,Aquisição de bandeiras.,Pregão - Eletrônico,2026-10-22 04:00:17,2026-11-06 09:59:00,23955.83,,Divulgada no PNCP,2026,https://pncp.gov.br/app/editais/00509968000148/2026/3623
```

- O CSV usa **UTF-8 com BOM**, para o Excel abrir os acentos certos com um duplo clique.
- As datas estão no formato `AAAA-MM-DD HH:MM:SS`, com o horário que vem da API.
- Os valores usam ponto como separador decimal. O `valor_homologado` vazio indica uma compra ainda sem resultado.

Para ver o mesmo conteúdo no banco, veja os exemplos em [Banco de dados](../como-funciona/banco.md#consultar-os-dados).


### `RUNBOOK.md`

```md
# Guia de Configuração e Execução

Este documento descreve como configurar e executar o projeto em um novo ambiente Databricks.

O objetivo é permitir que integrantes da equipe, professor ou avaliadores consigam reproduzir a solução utilizando apenas o repositório do GitHub.

> Este arquivo será atualizado conforme novas etapas da pipeline forem implementadas.

---

# 1. Repositório

Repositório oficial:

`https://github.com/Andre2217/ProjetoFinalEngDados`

No Databricks, crie uma Git Folder conectada ao repositório.

Após conectar, confirme que os arquivos do projeto estão disponíveis.

Estrutura mínima esperada:

ProjetoFinalEngDados/

notebooks/
- 00_setup.sql
- 01_landing.py
- 02_landing_to_bronze.py
- 03_quality_report.sql
- 04_bronze_to_silver.py
- 05_silver_to_gold.py

requirements.txt

README.md

RUNBOOK.md

---

# 2. Criar estrutura do Unity Catalog

Execute uma única vez:

`notebooks/00_setup.sql`

O arquivo deve criar:

Catalog:

`hackernews`

Schema:

`hacker_news`

Volume:

`data`

Comandos principais:

```sql
CREATE CATALOG IF NOT EXISTS hackernews;

CREATE SCHEMA IF NOT EXISTS hackernews.hacker_news;

CREATE VOLUME IF NOT EXISTS hackernews.hacker_news.data;
```
Após a execução, confirme no Catalog Explorer:
```
hackernews → hacker_news → Volumes → data
```

### 3. Testar a Landing
Abra:
`
notebooks/01_landing.py
`

Execute o notebook.

Ele deve realizar:

Hacker News API -> consulta das Top Stories
-> 
consulta dos detalhes de cada notícia
-> 
geração de NDJSON
-> 
Unity Catalog Volume

Os dados devem aparecer em:

`/Volumes/hackernews/hacker_news/data/landing`

A organização esperada é:

`landing/AAAA/MM/DD/arquivo.ndjson`

Exemplo:

`landing/2026/09/12/hacker_news_103000.ndjson`

É possível verificar os arquivos através do Catalog Explorer.

### 4. Criar o ETL Pipeline Landing → Bronze

Esta configuração precisa ser feita uma vez em cada workspace Databricks.

A configuração criada na interface de um usuário não é transferida automaticamente através do Git.

Acesse:

`Jobs & Pipelines`

Selecione:

`New → ETL Pipeline`

Nome sugerido:

`Hacker News - Landing to Bronze`

Configure o destino padrão:

Catalog:

`hackernews`

Schema:

`hacker_news`

Adicione como código-fonte:

`notebooks/02_landing_to_bronze.py`

Se o Databricks adicionar automaticamente arquivos de exemplo ao pipeline, remova-os das fontes.

O pipeline deve utilizar compute Serverless quando essa for a opção disponível no workspace.

### 5. Configurar Event Log

Dentro das configurações do ETL Pipeline, publique o Event Log no Unity Catalog.

Configure:

Catalog:

`hackernews`

Schema:

`hacker_news`

Nome:

`pipeline_event_log`

O resultado será:

`hackernews.hacker_news.pipeline_event_log`

Esse Event Log será utilizado como histórico oficial das execuções e das métricas de qualidade.

### 6. Validar o ETL Pipeline

Antes da primeira execução completa, utilize:

Dry run

O Dry Run valida a definição do pipeline.

Se não houver erros, execute:

Run pipeline

Na primeira execução, o Auto Loader deverá processar todos os arquivos existentes na Landing.

Nas execuções seguintes, apenas novos arquivos serão processados.

Ao final, devem existir no Catalog Explorer:

``` 
hackernews.hacker_news.bronze_stories

hackernews.hacker_news.quarantine_stories

hackernews.hacker_news.pipeline_event_log
```
### 7. Validar a Bronze

Abra:

`Catalog Explorer → hackernews → hacker_news → bronze_stories`

A tabela contém apenas registros aprovados pelas regras de qualidade.

Caso seja necessário visualizar os registros através de Sample Data, o Databricks poderá solicitar a inicialização de um SQL Warehouse.

No ambiente Free Edition normalmente será utilizado o:

Serverless Starter Warehouse

Isso é esperado.

O SQL Warehouse é utilizado para consultar os dados e não é o compute responsável pela execução do ETL Pipeline.

### 8. Validar a Quarentena

Abra:

`hackernews.hacker_news.quarantine_stories`

Essa tabela contém registros que não passaram nas regras de qualidade.

Ela também contém informações que permitem identificar o motivo da rejeição.

A existência da tabela de quarentena garante que registros problemáticos não sejam descartados silenciosamente.

### 8.1. Adicionar a Silver ao ETL Pipeline

A Silver não exige a criação de nenhum objeto novo no workspace.

O arquivo `notebooks/04_bronze_to_silver.py` é adicionado ao **mesmo** ETL Pipeline criado no passo 4 (`Hacker News - Landing to Bronze`).

Isso é necessário porque o código lê a tabela `bronze_stories` pelo nome curto, o que só funciona dentro do mesmo pipeline. O Lakeflow identifica sozinho a dependência Bronze → Silver.

Pré-requisito: os passos 1 a 8 já executados, com dados na `bronze_stories`.

Passo a passo:

1. Atualize o Git Folder com `Pull` e confirme que o arquivo `notebooks/04_bronze_to_silver.py` está disponível.
2. Abra o ETL Pipeline `Hacker News - Landing to Bronze`.
3. No painel de arquivos à esquerda, selecione a aba `All files`.
4. Navegue até `notebooks/04_bronze_to_silver.py`.
5. Nos três pontinhos do arquivo, selecione `Include in pipeline`.
6. Confirme que o arquivo aparece na aba `Pipeline`, junto com o `02_landing_to_bronze.py`.

Não é necessário criar a tabela manualmente. Na primeira execução, o pipeline cria a `silver_story_snapshots` em `hackernews.hacker_news`.

### 8.2. Executar e validar a Silver

Execute:

Dry run

No `Pipeline graph`, deve aparecer o fluxo:

```
landing_prepared → landing_validated → bronze_stories → silver_story_snapshots
                                     → quarantine_stories
```

Se não houver erros, execute:

Run pipeline

Na primeira execução, a Silver processa todos os registros já existentes na Bronze. Nas execuções seguintes, apenas os registros novos.

Ao final, deve existir no Catalog Explorer:

```
hackernews.hacker_news.silver_story_snapshots
```

Validações no SQL Editor:

Quantidade de linhas da Silver deve ser igual à da Bronze:

```sql
SELECT
  (SELECT COUNT(*) FROM hackernews.hacker_news.bronze_stories) AS bronze,
  (SELECT COUNT(*) FROM hackernews.hacker_news.silver_story_snapshots) AS silver;
```

Não deve haver duplicidade de notícia no mesmo snapshot (resultado esperado: nenhuma linha):

```sql
SELECT story_id, collected_at, COUNT(*) AS qtd
FROM hackernews.hacker_news.silver_story_snapshots
GROUP BY story_id, collected_at
HAVING COUNT(*) > 1;
```

Quantidade de snapshots e de notícias distintas:

```sql
SELECT
  COUNT(DISTINCT collected_at) AS snapshots,
  COUNT(DISTINCT story_id) AS noticias,
  COUNT(*) AS linhas
FROM hackernews.hacker_news.silver_story_snapshots;
```

Granularidade da tabela: uma linha por notícia em cada snapshot (chave lógica: `story_id` + `collected_at`).

Para popular a Silver com novos dados manualmente:

1. Execute `notebooks/01_landing.py` (gera um novo snapshot na Landing).
2. Execute o ETL Pipeline com `Run pipeline` (processa Landing → Bronze → Silver).

Recomenda-se gerar alguns snapshots com alguns minutos de intervalo, para que a mesma notícia apareça em coletas diferentes e seja possível observar a evolução de rank, score e comentários.

Observação sobre o Job: nenhuma alteração é necessária. A task `landing_to_bronze` executa o ETL Pipeline inteiro, portanto também passa a atualizar a Silver.

Observação sobre o Git Folder: o pipeline executa o código da branch ativa no Git Folder. Confirme a branch antes de executar.

### 8.3. Adicionar a Gold ao ETL Pipeline

Assim como a Silver, a Gold não exige a criação de nenhum objeto novo no workspace.

O arquivo `notebooks/05_silver_to_gold.py` é adicionado ao **mesmo** ETL Pipeline (`Hacker News - Landing to Bronze`), pois lê a tabela `silver_story_snapshots` pelo nome curto.

Pré-requisito: os passos 8.1 e 8.2 já executados, com dados na `silver_story_snapshots`.

Passo a passo:

1. Atualize o Git Folder com `Pull` e confirme que o arquivo `notebooks/05_silver_to_gold.py` está disponível.
2. Abra o ETL Pipeline `Hacker News - Landing to Bronze`.
3. No painel de arquivos à esquerda, selecione a aba `All files`.
4. Navegue até `notebooks/05_silver_to_gold.py`.
5. Nos três pontinhos do arquivo, selecione `Include in pipeline`.
6. Confirme que o arquivo aparece na aba `Pipeline`, junto com o `02_landing_to_bronze.py` e o `04_bronze_to_silver.py`.

Não é necessário criar as tabelas manualmente. Na primeira execução, o pipeline cria as quatro tabelas da Gold em `hackernews.hacker_news`.

### 8.4. Executar e validar a Gold

Execute:

Dry run

No `Pipeline graph`, deve aparecer o fluxo:

```
silver_story_snapshots → gold_story_timeline → gold_story_summary → gold_domain_stats
                                             → gold_trend_index
```

Se não houver erros, execute:

Run pipeline

As tabelas da Gold são materialized views. A cada execução, são atualizadas considerando todo o conteúdo atual da Silver.

Ao final, devem existir no Catalog Explorer:

```
hackernews.hacker_news.gold_story_timeline

hackernews.hacker_news.gold_story_summary

hackernews.hacker_news.gold_domain_stats

hackernews.hacker_news.gold_trend_index
```

Validações no SQL Editor:

A timeline deve ter a mesma quantidade de linhas da Silver, e o summary uma linha por notícia distinta:

```sql
SELECT
  (SELECT COUNT(*) FROM hackernews.hacker_news.silver_story_snapshots) AS silver_linhas,
  (SELECT COUNT(*) FROM hackernews.hacker_news.gold_story_timeline) AS timeline_linhas,
  (SELECT COUNT(DISTINCT story_id) FROM hackernews.hacker_news.silver_story_snapshots) AS silver_noticias,
  (SELECT COUNT(*) FROM hackernews.hacker_news.gold_story_summary) AS summary_linhas;
```

O Índice de Tendência deve conter somente notícias do snapshot mais recente:

```sql
SELECT
  (SELECT COUNT(*) FROM hackernews.hacker_news.gold_trend_index) AS noticias_no_indice,
  (SELECT COUNT(*)
   FROM hackernews.hacker_news.silver_story_snapshots
   WHERE collected_at = (SELECT MAX(collected_at) FROM hackernews.hacker_news.silver_story_snapshots)
  ) AS noticias_no_ultimo_snapshot;
```

Consultas de exploração:

```sql
-- Notícias em alta no momento
SELECT trend_rank, trend_index, title, rank, score, comments
FROM hackernews.hacker_news.gold_trend_index
ORDER BY trend_rank;

-- Evolução de uma notícia
SELECT collected_at, rank, score, comments, rank_change, score_delta
FROM hackernews.hacker_news.gold_story_timeline
WHERE story_id = '<story_id>'
ORDER BY collected_at;

-- Notícias com mais tempo no Top 10
SELECT title, hours_in_top_n, best_rank, peak_score
FROM hackernews.hacker_news.gold_story_summary
ORDER BY hours_in_top_n DESC;

-- Domínios mais recorrentes
SELECT domain, stories_count, stories_reached_top_n, avg_peak_score
FROM hackernews.hacker_news.gold_domain_stats
ORDER BY stories_count DESC;
```

Parâmetros como Top N, janela do Índice de Tendência e pesos dos componentes ficam em constantes no início do `05_silver_to_gold.py`. Após alterá-los, basta executar o pipeline novamente.

Observação sobre o Job: nenhuma alteração é necessária. A task do pipeline passa a atualizar também a Gold.

### 9. Criar views do relatório de qualidade

Após a primeira execução bem-sucedida do ETL Pipeline, execute uma única vez:

`notebooks/03_quality_report.sql`

Esse arquivo cria views sobre o Event Log.

As principais views são:

`hackernews.hacker_news.pipeline_runs

hackernews.hacker_news.quality_expectations`

O arquivo SQL não precisa ser executado a cada atualização da pipeline.

As views consultam diretamente o `pipeline_event_log.`

Portanto:

Pipeline executa novamente
↓
Event Log recebe novos eventos
↓
Views passam automaticamente a mostrar os novos dados

O SQL só precisa ser executado novamente caso a definição das views seja alterada.

### 10. Consultar histórico das execuções

Após criar as views:

```sql
SELECT *
FROM hackernews.hacker_news.pipeline_runs
ORDER BY started_at DESC;
```

Essa view permite acompanhar informações como:

- início da execução;
- fim da execução;
- status;
- registros enviados para Bronze;
- registros enviados para Quarentena;
- total processado;
- percentual de registros válidos.
### 11. Consultar regras de qualidade

Execute:

```sql
SELECT *
FROM hackernews.hacker_news.quality_expectations
ORDER BY processed_at DESC, expectation;
```

Essa view permite acompanhar cada regra de qualidade e quantos registros:

- passaram;
- falharam;
- percentual de sucesso.
### 12. Criar a orquestração

Após validar Landing e Landing → Bronze separadamente, crie um Lakeflow Job.

Acesse:

`Jobs & Pipelines → New → Job`

Nome sugerido:

`Hacker News Pipeline`

### Task 1 — Landing

Nome:

landing

Tipo:

Notebook

Arquivo:

notebooks/01_landing.py

Essa task consulta a API e cria um novo snapshot NDJSON na Landing.

Task 2 — Landing para Bronze

Nome:

landing_to_bronze

Tipo:

Pipeline

Pipeline:

Hacker News - Landing to Bronze

Dependência:

landing

Ou seja:

landing
↓
landing_to_bronze

A segunda task somente deve executar após o sucesso da primeira.

### 13. Testar o Job

Antes de configurar o agendamento automático, execute o Job manualmente.

O fluxo esperado é:

Task 1
Hacker News API
↓
novo arquivo NDJSON

Task 2
novo arquivo da Landing
↓
Auto Loader
↓
validação
↓
Bronze ou Quarentena

Após a execução, consulte:

bronze_stories

quarantine_stories

pipeline_runs

### 14. Agendamento

O agendamento definitivo será configurado após a pipeline completa estar estabilizada.

Planejamento atual:

Execução a cada 30 minutos.

Também será configurado:

retry em caso de falha;
dependências entre tasks;
registro de status;
monitoramento das execuções.

Por enquanto, durante o desenvolvimento, recomenda-se executar manualmente.

### 15. Como o processamento incremental funciona

A Landing mantém todos os snapshots.

Exemplo:

landing/

arquivo_1000.ndjson
arquivo_1030.ndjson
arquivo_1100.ndjson

Na primeira execução do ETL Pipeline:

arquivo_1000 → processado;
arquivo_1030 → processado;
arquivo_1100 → processado.

Posteriormente é criado:

arquivo_1130.ndjson.

Na próxima execução:

arquivo_1000 → ignorado;
arquivo_1030 → ignorado;
arquivo_1100 → ignorado;
arquivo_1130 → processado.

Esse comportamento é controlado pelo Auto Loader e pelo estado do Lakeflow Pipeline.

Não é necessário apagar nem mover os arquivos antigos da Landing.

### 16. Atualizar código pelo Git

Antes de começar a trabalhar:
```bash
git pull
```
Após realizar alterações:
```bash
git status
git add .
git commit -m "descricao da alteracao"
git push
```
Os objetos criados diretamente no workspace, como Jobs e ETL Pipelines, ainda não são versionados automaticamente pelo Git.

Nesta fase do projeto, a configuração necessária para recriá-los está documentada neste arquivo.

Posteriormente poderá ser utilizado Databricks Declarative Automation Bundles para versionar também a infraestrutura e a configuração dos Jobs e Pipelines.

### 17. Estado atual da execução

Atualmente o fluxo reproduzível é:

00_setup.sql

↓

01_landing.py

↓

Hacker News - Landing to Bronze

utilizando:

02_landing_to_bronze.py

↓

Bronze / Quarentena / Event Log

↓

03_quality_report.sql

↓

Views de monitoramento

↓

Lakeflow Job:

landing
↓
landing_to_bronze

### 18. Próximas etapas

Ainda serão adicionadas ao projeto:

Silver
↓
Gold
↓
Streamlit

Quando essas etapas forem implementadas, este RUNBOOK será atualizado com:

- novas tabelas;
- novas tasks do Job;
- novos passos de configuração;
- novos testes de validação;
- instruções para execução da solução completa.
### Resumo da primeira configuração

Em um workspace novo, a ordem é:

 Conectar o repositório GitHub ao Databricks.
Executar 00_setup.sql.
Executar 01_landing.py.
Criar o ETL Pipeline apontando para 02_landing_to_bronze.py.
Configurar Catalog hackernews e Schema hacker_news.
Publicar pipeline_event_log.
Fazer Dry Run.
Executar o ETL Pipeline.
Incluir 04_bronze_to_silver.py no mesmo ETL Pipeline.
Executar o ETL Pipeline novamente e validar silver_story_snapshots.
Incluir 05_silver_to_gold.py no mesmo ETL Pipeline.
Executar o ETL Pipeline novamente e validar as tabelas da Gold.
Executar 03_quality_report.sql uma única vez.
Criar o Lakeflow Job.
Configurar a task landing.
Configurar a task landing_to_bronze.
Executar o Job manualmente.
Validar Bronze, Quarentena e relatórios.

Após essa configuração inicial, a execução normal acontece através do Lakeflow Job.
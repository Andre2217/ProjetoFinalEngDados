# Pipeline de Monitoramento e Detecção de Tendências Tecnológicas no Hacker News

Projeto desenvolvido para a disciplina de **Projetos da Pós-Graduação em Engenharia de Dados da UNIFOR**.

## Objetivo

Construir uma pipeline de Engenharia de Dados capaz de coletar periodicamente as principais notícias do Hacker News, armazenar snapshots históricos e transformar esse fluxo de dados em indicadores que permitam identificar tendências tecnológicas.

A proposta não é apenas apresentar as notícias atuais, mas acompanhar sua evolução ao longo do tempo.

Entre as análises previstas estão:

- evolução do score;
- evolução da quantidade de comentários;
- evolução da posição no ranking;
- tempo de permanência no Top N;
- notícias com maior crescimento;
- fontes e domínios mais recorrentes;
- temas com maior engajamento;
- tendências emergentes;
- criação de um Índice de Tendência.

---

## Fonte de dados

A fonte utilizada é a API pública oficial do Hacker News, disponibilizada através do Firebase.

Principais endpoints utilizados:

- `/topstories.json`
- `/item/{id}.json`

A API é pública e não exige API Key.

---

## Arquitetura

A arquitetura geral planejada é:

Hacker News API  
↓  
Landing  
↓  
Bronze  
↓  
Silver  
↓  
Gold  
↓  
Streamlit

O processamento, armazenamento estruturado e orquestração são realizados dentro da plataforma Databricks.

### Fluxo atual implementado

Hacker News API  
↓  
Databricks  
↓  
Landing em NDJSON  
↓  
Auto Loader  
↓  
Padronização com Spark  
↓  
Expectations do Lakeflow  
↓  
Bronze / Quarentena  
↓  
Silver (snapshots limpos e tipados)  
↓  
Gold (indicadores analíticos)  
↓  
Event Log de qualidade

---

## Camadas

### Landing

A Landing preserva os dados provenientes da API o mais próximo possível do formato original.

Cada execução consulta as principais notícias do Hacker News e gera um novo snapshot em formato NDJSON.

Cada linha representa uma notícia observada naquele momento.

Os arquivos são armazenados no Unity Catalog Volume:

`/Volumes/hackernews/hacker_news/data/landing`

A organização utiliza partições de diretório por data:

`landing/AAAA/MM/DD/hacker_news_HHMMSS.ndjson`

Exemplo:

`landing/2026/09/12/hacker_news_103000.ndjson`

Os snapshots da Landing não são sobrescritos, permitindo construir o histórico necessário para as análises futuras.

---

### Bronze

A Bronze contém os registros da Landing que passaram pelas regras de qualidade.

A ingestão da Landing para a Bronze utiliza o Auto Loader do Databricks.

Isso permite processamento incremental:

- na primeira execução, são processados os arquivos existentes;
- nas execuções seguintes, somente arquivos ainda não processados são considerados.

Antes de serem persistidos, os dados passam por:

- tipagem;
- padronização;
- flatten do JSON;
- seleção das colunas necessárias;
- validações de qualidade.

Campos que não possuem utilidade analítica para o projeto, como `kids`, permanecem preservados na Landing, mas não são propagados para a Bronze.

A Bronze é persistida como tabela Delta:

`hackernews.hacker_news.bronze_stories`

Principais campos:

- record_key;
- collected_at;
- source;
- list_type;
- rank;
- story_id;
- title;
- author;
- url;
- domain;
- text;
- score;
- comments;
- published_at;
- item_type;
- source_file;
- source_file_modified_at;
- bronze_loaded_at.

---

### Quarentena

Registros que não atendem às regras de qualidade não são descartados silenciosamente.

Eles são direcionados para:

`hackernews.hacker_news.quarantine_stories`

A tabela preserva o registro problemático, sua origem e as regras de qualidade que foram violadas.

Isso permite investigar problemas sem interromper ou comprometer a camada Bronze.

---

### Silver

A camada Silver será responsável pela consolidação histórica dos snapshots.

A ideia é manter uma estrutura limpa e consistente em que uma mesma notícia possa aparecer em diferentes momentos de coleta.

Isso permitirá observar, por exemplo:

- score às 10:00;
- score às 10:30;
- score às 11:00;
- posição no ranking em cada coleta;
- número de comentários em cada coleta.

A Silver é implementada no arquivo `notebooks/04_bronze_to_silver.py`, dentro do mesmo Lakeflow ETL Pipeline da Bronze.

A leitura da Bronze é feita em streaming, portanto o processamento também é incremental: a cada execução, somente os registros novos da Bronze são processados.

A Silver é persistida como tabela Delta:

`hackernews.hacker_news.silver_story_snapshots`

Granularidade: uma linha por notícia em cada snapshot (chave lógica: `story_id` + `collected_at`).

As transformações são aplicadas de forma genérica, orientadas por configuração, na seguinte ordem:

1. **Seleção de colunas:** apenas as colunas necessárias para as análises são mantidas.
2. **Remoção de espaços:** `trim` no início e no fim das colunas `title`, `author`, `url`, `domain` e `source_file`. Valores que ficam vazios após o trim são convertidos para nulo.
3. **Tipagem explícita:** cada coluna recebe o tipo definido para a camada.
4. **Deduplicação:** registros com o mesmo `record_key` são descartados, protegendo a tabela contra o reprocessamento de um mesmo arquivo.
5. **Auditoria:** inclusão da coluna `silver_loaded_at`.

Campos como `source`, `list_type` e `item_type` são constantes validadas na Bronze e, por isso, não são propagados para a Silver. O campo `text` também não é propagado.

Colunas e tipos:

| Coluna | Tipo |
|---|---|
| record_key | string |
| collected_at | timestamp |
| rank | int |
| story_id | string |
| title | string |
| author | string |
| url | string |
| domain | string |
| score | int |
| comments | int |
| published_at | timestamp |
| source_file | string |
| source_file_modified_at | timestamp |
| bronze_loaded_at | timestamp |
| silver_loaded_at | timestamp |

#### Qualidade na Silver

Após a tipagem, a Silver aplica Expectations do tipo `expect_all_or_drop`. Como uma conversão de tipo que falha resulta em valor nulo, essas regras descartam registros inconsistentes e registram as métricas no Event Log:

- `record_key` obrigatório;
- `story_id` obrigatório;
- `collected_at` obrigatório;
- `rank` obrigatório;
- `title` obrigatório;
- `published_at` obrigatório.

---

### Gold

A camada Gold será responsável pelas regras analíticas e indicadores finais.

Entre as métricas previstas estão:

- crescimento de score;
- crescimento de comentários;
- variação de ranking;
- tempo de permanência no Top 10;
- notícias com crescimento mais rápido;
- domínios mais recorrentes;
- tendências por período;
- Índice de Tendência.

A Gold é implementada no arquivo `notebooks/05_silver_to_gold.py`, dentro do mesmo Lakeflow ETL Pipeline da Bronze e da Silver.

As tabelas da Gold são **materialized views**. A cada execução do pipeline, elas são atualizadas considerando todo o conteúdo atual da Silver, incluindo os snapshots recém-processados. Isso é necessário porque métricas como pico de score, tempo no ranking e Índice de Tendência dependem do histórico completo.

Os parâmetros analíticos ficam em constantes no início do arquivo, permitindo ajustes sem alterar a lógica:

- `TOP_N_HIGHLIGHT = 10`: faixa de destaque do ranking (Top 10);
- `TREND_WINDOW_HOURS = 6`: janela recente usada no Índice de Tendência;
- `MIN_AGE_HOURS = 1.0`: idade mínima usada nas velocidades, para não inflar notícias recém-publicadas;
- `TREND_WEIGHTS`: pesos dos componentes do Índice de Tendência.

Fluxo entre as tabelas:

```
silver_story_snapshots → gold_story_timeline → gold_story_summary → gold_domain_stats
                                             → gold_trend_index
```

#### gold_story_timeline

`hackernews.hacker_news.gold_story_timeline`

Granularidade: uma linha por notícia em cada snapshot (chave: `story_id` + `collected_at`).

Compara cada snapshot da notícia com o snapshot anterior da mesma notícia:

- `rank_change`: variação de posição (positivo significa que a notícia subiu);
- `score_delta` e `comments_delta`: variação de score e de comentários;
- `minutes_since_prev`: tempo real desde a coleta anterior;
- `score_per_hour_interval` e `comments_per_hour_interval`: velocidade no intervalo;
- `score_per_hour_lifetime`: score dividido pela idade da notícia;
- `age_hours`: idade da notícia no momento da coleta;
- `is_top_n`: se a notícia estava no Top 10 naquela coleta;
- `is_consecutive`: se a notícia também estava presente na coleta imediatamente anterior.

Como os intervalos entre coletas podem ser irregulares, todas as velocidades são calculadas pelo tempo real entre coletas, e não pela quantidade de snapshots.

Atende às análises de evolução do score, dos comentários e da posição no ranking.

#### gold_story_summary

`hackernews.hacker_news.gold_story_summary`

Granularidade: uma linha por notícia (chave: `story_id`).

Resume a passagem de cada notícia pelo ranking:

- primeira e última aparição (`first_seen_at`, `last_seen_at`);
- `is_in_latest_snapshot`: se a notícia ainda está no snapshot mais recente;
- `hours_in_ranking` e `hours_in_top_n`: tempo de permanência no ranking e no Top 10;
- melhor rank, rank inicial e rank final;
- pico, valor inicial e valor final de score e de comentários;
- `score_gain` e `comments_gain`: ganho durante o período observado;
- `score_gain_per_hour` e `comments_gain_per_hour`: ganho médio por hora.

O tempo de permanência é calculado pela soma dos intervalos entre coletas consecutivas em que a notícia estava presente (`is_consecutive`). Assim, uma notícia que sai do ranking e retorna depois não tem o período de ausência contabilizado.

Atende às análises de tempo de permanência no Top N e de notícias com maior crescimento, evitando que uma mesma notícia seja contada várias vezes.

#### gold_domain_stats

`hackernews.hacker_news.gold_domain_stats`

Granularidade: uma linha por domínio.

- `stories_count`: quantidade de notícias distintas que chegaram ao ranking;
- `stories_reached_top_n`: quantas chegaram ao Top 10;
- melhor rank alcançado;
- pico de score médio e máximo;
- pico de comentários médio;
- tempo médio no ranking.

Permite diferenciar domínios que aparecem com frequência de domínios que apresentam melhor desempenho.

Notícias sem link externo (por exemplo, posts do tipo Ask HN) são agrupadas como `(post sem link)`.

#### gold_trend_index

`hackernews.hacker_news.gold_trend_index`

Granularidade: uma linha por notícia presente no snapshot mais recente.

O Índice de Tendência (0 a 100) indica quais notícias estão ganhando força no momento, considerando as últimas 6 horas de coleta.

Cada componente é normalizado de 0 a 1 com `percent_rank`, com base na posição relativa entre as notícias do snapshot atual, e ponderado:

| Componente | Peso | Descrição |
|---|---|---|
| Velocidade de score | 40% | score dividido pela idade da notícia |
| Velocidade de comentários | 25% | comentários divididos pela idade da notícia |
| Momentum de ranking | 20% | posição no início da janela menos a posição atual |
| Posição atual | 15% | quanto melhor o rank atual, maior o valor |

A recência da publicação já está considerada nas velocidades, por isso não é um componente separado.

A tabela também expõe os valores normalizados de cada componente (`*_pct`), permitindo explicar por que cada notícia recebeu seu índice.

O índice é descritivo: indica o momento atual de cada notícia e não representa uma previsão de permanência ou entrada no Top 10.

#### Limitações da Gold

- As métricas refletem apenas o período em que a notícia esteve no ranking coletado. Quando uma notícia sai do ranking, sua evolução deixa de ser acompanhada.
- O tempo de permanência considera que a notícia esteve presente durante todo o intervalo entre duas coletas consecutivas. Com coletas a cada 30 minutos, essa aproximação é adequada.
- A qualidade das análises depende do volume de snapshots acumulados.

---

## Qualidade de dados

A qualidade é implementada através das **Expectations nativas do Lakeflow Declarative Pipelines**.

Entre as regras aplicadas atualmente estão:

- `story_id` obrigatório e positivo;
- `story_id` compatível com o ID retornado pelo item;
- data de coleta válida;
- ranking dentro da faixa esperada;
- título obrigatório;
- score não negativo;
- quantidade de comentários não negativa;
- data de publicação válida;
- origem dos dados esperada;
- tipo de lista esperado;
- item do tipo `story`;
- registros não deletados ou mortos;
- compatibilidade com o schema definido;
- JSON válido.

Registros aprovados seguem para a Bronze.

Registros reprovados seguem para a Quarentena.

Na camada Silver, novas Expectations validam o resultado da tipagem (ver seção **Qualidade na Silver**).

A camada Gold não aplica novas Expectations, pois é construída exclusivamente sobre dados já validados na Silver.

---

## Monitoramento e auditoria

O Lakeflow mantém automaticamente um Event Log das execuções do pipeline.

O log foi publicado no Unity Catalog como:

`hackernews.hacker_news.pipeline_event_log`

Ele registra informações como:

- horário das execuções;
- status;
- identificador da atualização;
- fluxos executados;
- quantidade de registros;
- resultados das Expectations;
- falhas e erros do pipeline.

Também são criadas views para facilitar a consulta dessas informações:

`hackernews.hacker_news.pipeline_runs`

`hackernews.hacker_news.quality_expectations`

Essas views permitem acompanhar o histórico de execução e qualidade sem depender de arquivos de log externos.

---

## Orquestração

A orquestração geral utiliza Lakeflow Jobs.

O fluxo inicial é:

Task 1 — Landing  
`01_landing.py`

↓  

Task 2 — Landing para Bronze e Silver  
Lakeflow ETL Pipeline utilizando `02_landing_to_bronze.py` e `04_bronze_to_silver.py`

Como a Silver faz parte do mesmo ETL Pipeline, o próprio Lakeflow resolve a dependência Bronze → Silver, sem necessidade de uma task adicional no Job.

A Gold também faz parte do mesmo ETL Pipeline (`05_silver_to_gold.py`). O Lakeflow resolve a dependência Silver → Gold, portanto a task do pipeline atualiza Bronze, Silver e Gold em sequência, sem necessidade de uma task adicional.

Futuramente serão adicionadas tarefas para:

Silver  
↓  
Gold  
↓  
Atualização da camada de consumo

O Job será responsável por:

- ordenar as dependências;
- executar as tarefas;
- realizar retries;
- registrar falhas;
- permitir agendamento periódico.

---

## Tecnologias

### Databricks

Plataforma principal da solução.

Responsável pelo desenvolvimento, processamento, armazenamento, pipelines e orquestração.

### Apache Spark

Utilizado para leitura, tipagem, transformação, padronização e processamento distribuído dos dados.

### Delta Lake

Utilizado na persistência das tabelas estruturadas, fornecendo confiabilidade e suporte a operações incrementais.

### Unity Catalog

Utilizado para organizar:

- Catalog;
- Schema;
- Volumes;
- tabelas;
- views;
- Event Logs.

Estrutura atual:

Catalog:

`hackernews`

Schema:

`hacker_news`

Volume:

`data`

---

### Auto Loader

Responsável pela ingestão incremental dos arquivos NDJSON existentes na Landing.

Permite processar somente novos arquivos sem reler todo o histórico a cada execução.

---

### Lakeflow Declarative Pipelines

Responsável pelo fluxo Landing → Bronze → Silver.

Com a Gold, o pipeline passa a cobrir o fluxo completo Landing → Bronze → Silver → Gold, utilizando streaming tables na Bronze e na Silver e materialized views na Gold.

Utiliza:

- Auto Loader;
- Spark;
- Expectations;
- tabelas Delta;
- Event Log;
- gerenciamento de estado incremental.

---

### Lakeflow Jobs

Responsável pela orquestração geral do projeto.

---

### Streamlit

Será utilizado como camada de consumo e visualização dos indicadores finais.

---

### pytest

Será utilizado para testes automatizados do código Python e das regras auxiliares do projeto.

---

### Git + GitHub

Utilizados para:

- versionamento;
- colaboração entre os integrantes;
- histórico de alterações;
- entrega do projeto.

Repositório:

`https://github.com/Andre2217/ProjetoFinalEngDados`

---

## Estrutura do projeto

ProjetoFinalEngDados/

notebooks/
- 00_setup.sql
- 01_landing.py
- 02_landing_to_bronze.py
- 03_quality_report.sql
- 04_bronze_to_silver.py
- 05_silver_to_gold.py

docs/
- architecture.md

tests/

requirements.txt

.gitignore

README.md

RUNBOOK.md

---

## Dependências externas

O arquivo `requirements.txt` contém apenas bibliotecas adicionais necessárias ao projeto.

Atualmente:

```txt
requests==2.32.5
pytest==8.4.2
streamlit==1.49.1
```

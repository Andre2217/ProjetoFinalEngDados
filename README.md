# Hacker News Trends

Base inicial do projeto da disciplina de Projetos da pós-graduação em Engenharia de Dados da UNIFOR.

## Objetivo desta versão

Esta versão implementa somente a primeira etapa real do pipeline:

**Hacker News API → Landing**

A Landing recebe o conteúdo da API sem limpeza, tipagem ou regra de negócio. O objetivo é preservar o dado coletado para que as próximas camadas possam ser reprocessadas sem consultar novamente a fonte.

## Arquitetura planejada

```text
Hacker News API
      ↓
   Landing
      ↓
Great Expectations
      ↓
   Bronze
      ↓
   Silver
      ↓
    Gold
      ↓
 Dashboard
```

O armazenamento definitivo ainda será decidido pela equipe. A estrutura permite evoluir para DuckDB, MinIO ou uma combinação dos dois sem alterar a lógica da fonte.

## Tecnologias planejadas

- Python + Requests: ingestão da API
- Apache Airflow: orquestração e agendamento
- Great Expectations: qualidade e validação de dados
- DuckDB: opção para dados estruturados e consultas analíticas
- MinIO: opção para armazenamento de objetos/arquivos
- Pandas: transformações simples
- Streamlit: consumo final
- Docker Compose: ambiente reproduzível
- Git/GitHub: versionamento

## Estrutura

```text
.
├── dags/
│   └── hacker_news_landing.py
├── src/
│   └── landing.py
├── data/
│   ├── landing/
│   ├── bronze/
│   ├── silver/
│   └── gold/
├── docs/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

## Executar

Crie o `.env`:

```bash
cp .env.example .env
```

Suba o Airflow:

```bash
docker compose up --build
```

Acesse:

```text
http://localhost:8080
```

O DAG `hacker_news_landing` está configurado para executar a cada 30 minutos.

A senha gerada pelo modo standalone do Airflow fica dentro do volume do Airflow. Para visualizá-la:

```bash
docker compose exec airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated
```

Os snapshots serão gravados em:

```text
data/landing/AAAA/MM/DD/
```

## MinIO

O MinIO está preparado, mas não é obrigatório nesta etapa. Para iniciá-lo junto com o Airflow:

```bash
docker compose --profile minio up --build
```

Console do MinIO:

```text
http://localhost:9001
```

Nesta versão a Landing ainda grava localmente. A decisão de usar MinIO, DuckDB ou ambos será tomada antes da implementação das próximas camadas.

# Arquitetura inicial

## Fluxo planejado

```text
Hacker News API
      ↓
Landing - dado bruto coletado
      ↓
Great Expectations - validação
      ↓
Bronze - dado validado
      ↓
Silver - dado estruturado e consolidado
      ↓
Gold - métricas e indicadores de tendência
      ↓
Streamlit
```

## Decisão atual

A única camada implementada nesta etapa é a Landing.

A equipe ainda vai decidir entre:

1. arquivos/objetos no MinIO para Landing e Bronze + DuckDB para Silver e Gold;
2. arquivos locais para Landing + DuckDB para camadas estruturadas;
3. outra combinação simples que mantenha as responsabilidades das camadas claras.

A estrutura do projeto evita acoplar a ingestão a uma dessas decisões antes da definição da equipe.

## Responsabilidade futura das camadas

**Landing:** cópia bruta da fonte, com horário de coleta.

**Bronze:** registros aceitos após regras de qualidade do Great Expectations, mantendo estrutura próxima da origem.

**Silver:** consolidação do histórico de snapshots em uma tabela estruturada com notícia, score, comentários, ranking, publicação e coleta.

**Gold:** métricas derivadas, como permanência no Top 10, crescimento de score/comentários, subida no ranking e notícias emergentes.

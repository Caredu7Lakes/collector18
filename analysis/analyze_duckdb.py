"""Camada de análise (read-only) do collector18 via DuckDB.

Lê o Postgres do coletor (Neon ou local) pela extensão `postgres` do DuckDB e roda
as análises de coleta e tratamento. NÃO escreve nada no banco (ATTACH READ_ONLY).

A extensão postgres do DuckDB usa string de conexão libpq (host/port/dbname/user/
password/sslmode) — não a URL asyncpg da app. Para o Neon, pegue os campos do painel.

Uso:
    export COLLECTOR_PG_DSN="host=ep-xxx.aws.neon.tech port=5432 dbname=neondb \
user=USER password=PASS sslmode=require"
    python analysis/analyze_duckdb.py

    # opcional: latência/fallback do extractor a partir do log da app
    COLLECTOR_LOG=/caminho/collector18.log python analysis/analyze_duckdb.py
"""

import os
import sys

import duckdb

PG_DSN = os.environ.get("COLLECTOR_PG_DSN")
if not PG_DSN:
    sys.exit("faltando COLLECTOR_PG_DSN (string libpq do Postgres do coletor)")

con = duckdb.connect()
con.execute("INSTALL postgres; LOAD postgres;")
con.execute(f"ATTACH '{PG_DSN}' AS pg (TYPE postgres, READ_ONLY);")


def show(titulo: str, sql: str) -> None:
    print(f"\n=== {titulo} ===")
    try:
        df = con.sql(sql).to_df()
        print(df.to_string(index=False) if not df.empty else "(sem linhas)")
    except Exception as e:  # análise não derruba por uma query vazia/ausente
        print(f"(erro: {e})")


show("Volume por dia e tipo", """
    SELECT received_at::date AS dia, message_type, count(*) AS msgs
    FROM pg.public.raw_messages
    GROUP BY 1, 2 ORDER BY 1, 3 DESC
""")

show("Funil de tratamento", """
    SELECT
      (SELECT count(*) FROM pg.public.raw_messages)                    AS raw,
      (SELECT count(*) FROM pg.public.indications)                     AS indications,
      (SELECT count(*) FROM pg.public.indications WHERE is_indication) AS indicacoes_validas,
      (SELECT count(*) FROM pg.public.contacts)                        AS contatos_vcard
""")

show("Taxa de indicação (texto)", """
    SELECT is_indication, count(*) AS n,
           round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct
    FROM pg.public.indications GROUP BY 1 ORDER BY 2 DESC
""")

show("Confiança do extractor (p50/p95)", """
    SELECT round(avg(confidence), 3)                 AS media,
           round(quantile_cont(confidence, 0.5), 3)  AS p50,
           round(quantile_cont(confidence, 0.95), 3) AS p95
    FROM pg.public.indications WHERE confidence IS NOT NULL
""")

show("Top serviços indicados", """
    SELECT lower(trim(servico_termo)) AS servico, count(*) AS n
    FROM pg.public.indications
    WHERE is_indication AND servico_termo IS NOT NULL
    GROUP BY 1 ORDER BY 2 DESC LIMIT 15
""")

show("Top recomendadores", """
    SELECT r.sender_name, count(*) AS indicacoes
    FROM pg.public.raw_messages r
    JOIN pg.public.indications i ON i.source_message_id = r.id
    WHERE i.is_indication
    GROUP BY 1 ORDER BY 2 DESC LIMIT 15
""")

show("Qualidade — ausências nas indicações válidas", """
    SELECT
      count(*) FILTER (WHERE provider_name IS NULL) AS sem_contato,
      count(*) FILTER (WHERE servico_termo IS NULL) AS sem_servico,
      count(*) FILTER (WHERE phone IS NULL)         AS sem_telefone,
      count(*)                                      AS total
    FROM pg.public.indications WHERE is_indication
""")

# Mostra o problema de telefone não-normalizado que vai pro import do Moshe:
# agrupa por dígitos p/ ver o MESMO número chegando em formatos diferentes.
show("Candidatos a dedup por telefone (só dígitos)", """
    WITH tel AS (
      SELECT regexp_replace(phone, '[^0-9]', '', 'g') AS d
      FROM pg.public.indications WHERE phone IS NOT NULL
      UNION ALL
      SELECT regexp_replace(unnest(phones), '[^0-9]', '', 'g')
      FROM pg.public.contacts
    )
    SELECT d AS telefone_digitos, count(*) AS ocorrencias
    FROM tel WHERE length(d) >= 8
    GROUP BY 1 HAVING count(*) > 1 ORDER BY 2 DESC LIMIT 20
""")

# Latência/fallback do extractor — opcional, lido do log (métricas 'metric=extract').
log = os.environ.get("COLLECTOR_LOG")
if log and os.path.exists(log):
    show("Extractor — latência e método (do log)", f"""
        WITH linhas AS (
          SELECT unnest(string_split(content, chr(10))) AS line
          FROM read_text('{log}')
        ), m AS (
          SELECT regexp_extract(line, 'method=(\\w+)', 1) AS metodo,
                 TRY_CAST(regexp_extract(line, 'latency_ms=([0-9.]+)', 1) AS DOUBLE) AS lat
          FROM linhas WHERE line LIKE '%metric=extract%'
        )
        SELECT metodo, count(*) AS n,
               round(avg(lat), 1)                 AS media_ms,
               round(quantile_cont(lat, 0.5), 1)  AS p50_ms,
               round(quantile_cont(lat, 0.95), 1) AS p95_ms
        FROM m GROUP BY 1 ORDER BY 2 DESC
    """)
else:
    print("\n(latência/fallback: defina COLLECTOR_LOG=<arquivo> p/ incluir métricas do extractor)")

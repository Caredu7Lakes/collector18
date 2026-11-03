import os

# Settings exige essas vars no boot; valores dummy para testes sem banco/segredos reais.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("WEBHOOK_TOKEN", "test-token")

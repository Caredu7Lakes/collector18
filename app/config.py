from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Neon (asyncpg). Ex.: postgresql+asyncpg://user:pass@host/db?ssl=require
    # NÃO usar sslmode=/channel_binding= (quebram o asyncpg); usar ?ssl=require.
    database_url: str

    # Token que o webhook da Evolution envia no header Authorization: Bearer <...>
    webhook_token: str

    # Extração por LLM (opcional: sem chave, cai no fallback heurístico)
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    # Timeout da chamada ao LLM. O webhook é inline e a Evolution derruba a entrega
    # em ~30s — manter folgado abaixo disso; ao estourar, cai no fallback heurístico.
    openai_timeout_seconds: float = 15.0

    # JIDs dos grupos a ingerir (vazio = todos os grupos). Fora de grupo é ignorado.
    allowed_group_jids: str = ""

    @property
    def allowed_groups(self) -> set[str]:
        return {j.strip() for j in self.allowed_group_jids.split(",") if j.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


from functools import lru_cache
from google.adk.models.lite_llm import LiteLlm

from src.config.settings import api_config


@lru_cache(maxsize=1)
def build_llm_client(model: str | None = None) -> LiteLlm:
    """
        Shared utilities for remote A2A microservices.
        Create (and cache) a LiteLlm client configured via environment settings.
    """
    return LiteLlm(
        model=model or api_config.llm_model,
        api_base=api_config.base_url_llm,
        api_key=api_config.api_key,
    )

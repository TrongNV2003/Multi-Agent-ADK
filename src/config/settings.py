from enum import Enum
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv(override=True)

class APIConfig(BaseSettings):
    base_url_llm: str = Field(
        description="Base URL for OpenAI API",
        alias="API_URL",
    )
    api_key: str = Field(
        description="API key for OpenAI",
        alias="API_KEY",
    )
    llm_model: str = Field(
        default="openai/Qwen/Qwen3-8B",
        description="Large Language model name to be used (e.g., GPT-4)",
        alias="LLM_MODEL",
    )

class LLMConfig(BaseSettings):
    gemini_api_key: str = Field(
        ...,
        description="API key for Gemini API",
        alias="GEMINI_API_KEY",
    )
    gemini_model: str = Field(
        default="gemini/gemini-1.5-flash",
        description="Model name to be used (e.g., Gemini-1.5)",
        alias="GEMINI_MODEL",
    )
    
    temperature: float = Field(
        default=0.0,
        description="Sampling temperature; higher values make output more random",
        alias="TEMPERATURE",
    )
    max_tokens: int = Field(
        default=512,
        alias="MAX_TOKENS",
        description="Maximum number of tokens for API responses",
    )
    top_p: float = Field(
        default=0.95,
        alias="TOP_P",
        description="Nucleus sampling parameter; higher values increase randomness",
    )
    seed: int = Field(default=42, alias="SEED", description="Random seed for sampling")


class MCPConfig(BaseSettings):
    mcp_url: str = Field(
        default="http://localhost:8000/sse",
        description="Base URL for MCP API",
        alias="MCP_SERVER_URL",
    )


class MongodbConfig(BaseSettings):
    mongo_uri: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB connection URI",
        alias="MONGODB_URI",
    )
    db_name: str = Field(
        default="inventory",
        description="Database name for MongoDB",
        alias="MONGODB_NAME",
    )


class A2AServiceConfig(BaseSettings):
    base_host: str = Field(
        default="http://localhost",
        description="Base host (with scheme) for all remote A2A agents",
        alias="A2A_BASE_HOST",
    )
    analysis_port: int = Field(
        default=9101,
        description="Port for Analysis Agent service",
        alias="A2A_ANALYSIS_PORT",
    )
    inventory_port: int = Field(
        default=9102,
        description="Port for Inventory Agent service",
        alias="A2A_INVENTORY_PORT",
    )
    order_port: int = Field(
        default=9103,
        description="Port for Order Agent service",
        alias="A2A_ORDER_PORT",
    )
    consultant_port: int = Field(
        default=9104,
        description="Port for Consultant Agent service",
        alias="A2A_CONSULTANT_PORT",
    )

    def build_agent_base(self, port: int) -> str:
        host = self.base_host.rstrip('/')
        return f"{host}:{port}"


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


api_config = APIConfig()
llm_config = LLMConfig()
mcp_config = MCPConfig()
db_config = MongodbConfig()
a2a_service_config = A2AServiceConfig()

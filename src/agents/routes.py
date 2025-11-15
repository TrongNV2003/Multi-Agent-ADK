from loguru import logger
from typing import Dict, Optional, Callable
from google.adk.agents.remote_a2a_agent import (
    AGENT_CARD_WELL_KNOWN_PATH,
    RemoteA2aAgent,
)

from src.config.settings import a2a_service_config


def _agent_card_url(port: int) -> str:
    """Build agent card URL for remote A2A agent"""
    return (
        f"{a2a_service_config.build_agent_base(port)}/"
        f"{AGENT_CARD_WELL_KNOWN_PATH}"
    )


# Registry - Manages all remote agents from A2A services
class AgentRegistry:
    """
    Central registry for remote A2A agents
    Acts as a service discovery layer for agent-to-agent communication
    """
    def __init__(self):
        self.agents: Dict[str, RemoteA2aAgent] = {}     # agent_name → RemoteA2aAgent
        self.handlers: Dict[str, Callable] = {}         # agent_name → handler function
        
    def register(
        self, 
        name: str,
        agent: RemoteA2aAgent,
        handler: Callable
    ):
        """
        Register a remote agent with its handler
        
        Args:
            name: Agent identifier (e.g., "inventory_agent")
            agent: RemoteA2aAgent instance
            handler: Async function to invoke this agent
        """
        self.agents[name] = agent
        self.handlers[name] = handler
        
        logger.info(f"[Registry] Registered agent: {name}")
        logger.debug(f"  Description: {agent.description}")
    
    def get_agent(self, agent_name: str) -> Optional[RemoteA2aAgent]:
        """Get RemoteA2aAgent instance by name"""
        return self.agents.get(agent_name)
    
    def get_handler(self, agent_name: str) -> Optional[Callable]:
        """Get handler function for an agent"""
        return self.handlers.get(agent_name)
    
    def list_agents(self) -> list[str]:
        """List all registered agent names"""
        return list(self.agents.keys())


# Remote Agent Wrappers
class AnalysisAgent:
    """Analysis Agent - Phân tích yêu cầu khách hàng"""
    def __init__(self):
        self.agent = RemoteA2aAgent(
            name="analysis_agent",
            description="Phân tích yêu cầu khách hàng và xác định workflow cần thiết",
            agent_card=_agent_card_url(a2a_service_config.analysis_port),
        )


class InventoryAgent:
    """Inventory Agent - Kiểm tra tồn kho và giá sản phẩm"""
    def __init__(self):
        self.agent = RemoteA2aAgent(
            name="inventory_agent",
            description="Kiểm tra tồn kho và giá sản phẩm từ database",
            agent_card=_agent_card_url(a2a_service_config.inventory_port),
        )


class OrderAgent:
    """Order Agent - Tạo và quản lý đơn hàng"""
    def __init__(self):
        self.agent = RemoteA2aAgent(
            name="order_agent",
            description="Tạo và quản lý đơn hàng cho khách",
            agent_card=_agent_card_url(a2a_service_config.order_port),
        )


class ConsultantAgent:
    """Consultant Agent - Tạo câu trả lời tự nhiên"""
    def __init__(self):
        self.agent = RemoteA2aAgent(
            name="consultant_agent",
            description="Tạo câu trả lời tự nhiên cho khách hàng",
            agent_card=_agent_card_url(a2a_service_config.consultant_port),
        )

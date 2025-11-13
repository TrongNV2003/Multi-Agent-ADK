import json
from loguru import logger
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, Callable

from google.genai import types
from google.adk.agents import Agent
from google.adk.planners import PlanReActPlanner


# AGENT CARD - Metadata and Interface
@dataclass
class AgentCard:
    name: str                          # Agent identifier (e.g., "inventory_agent")
    display_name: str                  # Human-readable name
    role: str                          # What this agent does
    capabilities: list[str]            # What tasks this agent can perform
    input_schema: Dict[str, Any]       # Expected input format (JSON Schema)
    output_schema: Dict[str, Any]      # Expected output format (JSON Schema)
    endpoint: Optional[str] = None     # For remote agents (URL/address)
    version: str = "1.0.0"
    metadata: Optional[Dict[str, Any]] = None
    
    def to_function_declaration(self) -> types.FunctionDeclaration:
        """
        Convert agent card to FunctionDeclaration so other agents can call it
        """
        return types.FunctionDeclaration(
            name=f"{self.name}",
            description=f"{self.role}\n\nCapabilities: {', '.join(self.capabilities)}",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    key: types.Schema(
                        type=self._json_type_to_genai_type(schema.get("type", "string")),
                        description=schema.get("description", "")
                    )
                    for key, schema in self.input_schema.items()
                }
            )
        )
    
    @staticmethod
    def _json_type_to_genai_type(json_type: str) -> types.Type:
        """Convert JSON Schema type to GenAI Type"""
        mapping = {
            "string": types.Type.STRING,
            "number": types.Type.NUMBER,
            "integer": types.Type.INTEGER,
            "boolean": types.Type.BOOLEAN,
            "object": types.Type.OBJECT,
            "array": types.Type.ARRAY
        }
        return mapping.get(json_type.lower(), types.Type.STRING)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return asdict(self)


# Manages all agent cards
class AgentRegistry:
    """
    Central registry where all agents register their cards
    Acts as a "phone book" for agent-to-agent communication
    """
    
    def __init__(self):
        self.cards: Dict[str, AgentCard] = {}           # agent_name → AgentCard
        self.handlers: Dict[str, Callable] = {}         # agent_name → handler function
        self.runners: Dict[str, Any] = {}               # agent_name → Runner instance
        
    def register(
        self, 
        card: AgentCard, 
        runner: Any,
        handler: Callable
    ):
        """
        Register an agent with its card
        
        Args:
            card: AgentCard describing the agent
            runner: The agent's Runner instance
            handler: Async function to invoke this agent
        """
        self.cards[card.name] = card
        self.runners[card.name] = runner
        self.handlers[card.name] = handler
        
        logger.info(f"[Registry] Registered agent: {card.display_name} ({card.name})")
        logger.debug(f"  Role: {card.role}")
        logger.debug(f"  Capabilities: {card.capabilities}")
    
    def get_card(self, agent_name: str) -> Optional[AgentCard]:
        """Get agent card by name"""
        return self.cards.get(agent_name)
    
    def get_handler(self, agent_name: str) -> Optional[Callable]:
        """Get handler function for an agent"""
        return self.handlers.get(agent_name)
    
    def get_runner(self, agent_name: str) -> Optional[Any]:
        """Get runner instance for an agent"""
        return self.runners.get(agent_name)
    
    def list_agents(self) -> list[AgentCard]:
        """List all registered agents"""
        return list(self.cards.values())
    
    def get_agent_declarations_for(self, agent_name: str) -> list[types.FunctionDeclaration]:
        """
        Get FunctionDeclarations for all OTHER agents (excluding self)
        This is used to give an agent the ability to call other agents
        """
        declarations = []
        for name, card in self.cards.items():
            if name != agent_name:  # Don't include self
                declarations.append(card.to_function_declaration())
        return declarations


# INDEPENDENT AGENTS (Each creates its own card)
class AnalysisAgent:
    """Analysis Agent - Independent, no need to call others"""
    
    CARD = AgentCard(
        name="analysis_agent",
        display_name="Analysis Agent",
        role="Phân tích yêu cầu khách hàng và xác định workflow cần thiết",
        capabilities=[
            "Phân tích ý định khách hàng",
            "Trích xuất thông tin sản phẩm",
            "Xác định workflow (check inventory, place order, etc.)"
        ],
        input_schema={
            "query": {
                "type": "string",
                "description": "Câu hỏi/yêu cầu của khách hàng"
            }
        },
        output_schema={
            "product_details": {"type": "string"},
            "customer_intent": {"type": "string"},
            "requires_inventory_check": {"type": "boolean"},
            "requires_order_placement": {"type": "boolean"}
        }
    )
    
    def __init__(self, client):
        self.planner = PlanReActPlanner()
        self.agent = Agent(
            name=self.CARD.name,
            model=client,
            description=self.CARD.role,
            instruction="""Bạn là Analysis Agent - phân tích yêu cầu khách hàng.

NHIỆM VỤ:
Phân tích câu hỏi và trả về JSON:
{
  "product_details": "Tên sản phẩm chi tiết",
  "customer_intent": "check_inventory_price | place_order | general_query",
  "original_query": "Câu hỏi gốc",
  "requires_inventory_check": true/false,
  "requires_order_placement": true/false
}

CHÚ Ý: Chỉ trả JSON thuần, KHÔNG dùng markdown
            """,
            planner=self.planner
        )


class InventoryAgent:
    """Inventory Agent - Independent agent that manages inventory"""
    
    CARD = AgentCard(
        name="inventory_agent",
        display_name="Inventory Agent",
        role="Kiểm tra tồn kho và giá sản phẩm từ database",
        capabilities=[
            "Truy vấn tồn kho sản phẩm",
            "Lấy thông tin giá",
            "Kiểm tra số lượng còn hàng"
        ],
        input_schema={
            "query": {
                "type": "string",
                "description": "Thông tin sản phẩm cần check (product, storage, color)"
            },
            "context": {
                "type": "string",
                "description": "Context từ analysis agent (JSON string)"
            }
        },
        output_schema={
            "product_name": {"type": "string"},
            "storage": {"type": "string"},
            "color": {"type": "string"},
            "stock_status": {"type": "string"},
            "price": {"type": "number"},
            "quantity": {"type": "integer"}
        }
    )
    
    def __init__(self, client):
        self.planner = PlanReActPlanner()
        self.agent = Agent(
            name=self.CARD.name,
            model=client,
            description=self.CARD.role,
            instruction="""Bạn là Inventory Agent - chuyên kiểm tra tồn kho.

NHIỆM VỤ:
1. Phân tích input để lấy: product, storage, color
2. Xác định thông tin sản phẩm cần truy vấn
3. Trả về JSON với format:
{
  "product_name": "...",
  "storage": "...",
  "color": "...",
  "query_needed": "check_inventory_detail",
  "query_params": {"product": "...", "storage": "...", "color": "..."}
}

Lưu ý: Bạn KHÔNG gọi tool trực tiếp. Handler sẽ gọi tool dựa trên output của bạn.
            """,
            planner=self.planner
        )


class OrderAgent:
    """Order Agent - Independent agent that creates orders"""
    
    CARD = AgentCard(
        name="order_agent",
        display_name="Order Agent",
        role="Tạo và quản lý đơn hàng cho khách",
        capabilities=[
            "Tạo đơn hàng mới",
            "Lưu thông tin đơn hàng",
            "Generate order ID"
        ],
        input_schema={
            "query": {
                "type": "string",
                "description": "Yêu cầu tạo đơn hàng"
            },
            "inventory_info": {
                "type": "string",
                "description": "Thông tin tồn kho từ inventory agent (JSON)"
            },
            "customer_info": {
                "type": "string",
                "description": "Thông tin khách hàng (JSON)"
            }
        },
        output_schema={
            "order_created": {"type": "boolean"},
            "order_details": {"type": "object"},
            "customer_info": {"type": "object"},
            "message": {"type": "string"}
        }
    )
    
    def __init__(self, client):
        self.planner = PlanReActPlanner()
        self.agent = Agent(
            name=self.CARD.name,
            model=client,
            description=self.CARD.role,
            instruction="""Bạn là Order Agent - chuyên tạo đơn hàng.

NHIỆM VỤ:
1. Nhận thông tin từ inventory và customer
2. Xác định thông tin cần tạo đơn hàng
3. Trả về JSON với format:
{
  "order_ready": true,
  "order_params": {
    "product": "...",
    "color": "...",
    "storage": "...",
    "quantity": 1,
    "price": số,
    "customer_name": "...",
    "customer_phone": "...",
    "customer_address": "..."
  }
}

Lưu ý: Bạn KHÔNG gọi tool trực tiếp. Handler sẽ gọi tool dựa trên output của bạn.
QUAN TRỌNG: Giữ ĐẦY ĐỦ color, storage trong order_params
TUÂN THỦ: Chỉ trả JSON thuần theo đúng format, không thêm mô tả, không dùng markdown, không viết code block.
            """,
            planner=self.planner
        )


class ConsultantAgent:
    """Consultant Agent - Generates final response"""
    
    CARD = AgentCard(
        name="consultant_agent",
        display_name="Consultant Agent",
        role="Tạo câu trả lời tự nhiên cho khách hàng",
        capabilities=[
            "Tổng hợp thông tin từ các agents",
            "Generate natural language response",
            "Định dạng thông tin thân thiện"
        ],
        input_schema={
            "query": {"type": "string"},
            "analysis": {"type": "string"},
            "inventory": {"type": "string"},
            "order": {"type": "string"},
            "coordinator_summary": {"type": "string"}
        },
        output_schema={
            "response": {"type": "string"}
        }
    )
    
    def __init__(self, client):
        self.planner = PlanReActPlanner()
        self.agent = Agent(
            name=self.CARD.name,
            model=client,
            description=self.CARD.role,
            instruction="""Bạn là Consultant Agent - tư vấn viên.

NHIỆM VỤ:
- Tổng hợp thông tin từ inventory agent (giá, tồn kho) và order agent (order ID, trạng thái đơn)
- Tạo câu trả lời hoàn chỉnh, thân thiện bằng tiếng Việt

YÊU CẦU:
- Trả lời trực tiếp, không đưa mã nguồn hay pseudo-code
- Dùng giọng điệu tự nhiên, tích cực; liệt kê rõ ràng thông tin sản phẩm và trạng thái đơn hàng
- Nếu thiếu dữ liệu, giải thích ngắn gọn và đề xuất bước tiếp theo cho khách

VÍ DỤ:
"Chào bạn! iPhone 15 Pro Max 256GB màu Titan tự nhiên hiện đang sẵn hàng với giá 27.990.000 VNĐ (còn 3 máy). 
Đơn hàng #order_123 của bạn đã được tạo thành công. Cảm ơn bạn đã tin tưởng!"
            """,
            planner=self.planner
        )

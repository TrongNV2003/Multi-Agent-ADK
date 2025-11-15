import uvicorn
from pydantic import BaseModel, Field
from a2a.types import AgentCard
from google.adk.agents import Agent
from google.adk.planners import PlanReActPlanner
from google.adk.a2a.utils.agent_to_a2a import to_a2a

from src.a2a_services.base import build_llm_client
from src.config.settings import a2a_service_config


class AnalysisInput(BaseModel):
    query: str = Field(..., description="Câu hỏi/yêu cầu của khách hàng")

class AnalysisOutput(BaseModel):
    product_details: str = Field(..., description="Tên sản phẩm chi tiết được trích xuất từ query")
    customer_intent: str = Field(..., description="Ý định khách hàng: check_inventory_price, place_order, hoặc general_query")
    original_query: str = Field(..., description="Câu hỏi gốc của khách hàng")
    requires_inventory_check: bool = Field(..., description="True nếu cần kiểm tra tồn kho")
    requires_order_placement: bool = Field(..., description="True nếu cần tạo đơn hàng")


planner = PlanReActPlanner()
analysis_agent = Agent(
    name="analysis_agent",
    model=build_llm_client(),
    description=(
        "Phân tích yêu cầu khách hàng và xác định workflow cần thiết trước khi"
        " điều phối các agent khác."
    ),
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
    planner=planner,
    input_schema=AnalysisInput,
    output_schema=AnalysisOutput
)

# Define Agent card according to A2A protocol
analysis_card = AgentCard(
    name="analysis_agent",
    url=a2a_service_config.build_agent_base(a2a_service_config.analysis_port),
    description="Phân tích yêu cầu khách hàng và xác định workflow cần thiết",
    version="1.0.0",
    capabilities={
        "intents": ["analyze_customer_query", "extract_product_info", "determine_workflow"]
    },
    skills=[],
    defaultInputModes=["text/plain"],
    defaultOutputModes=["application/json"],
    supportsAuthenticatedExtendedCard=False,
)

a2a_app = to_a2a(analysis_agent, port=a2a_service_config.analysis_port, agent_card=analysis_card)
app = a2a_app


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=a2a_service_config.analysis_port,
        log_level="info",
    )

"""
python -m src.a2a_services.analysis_agent
"""
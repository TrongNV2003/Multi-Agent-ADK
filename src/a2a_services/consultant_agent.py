import uvicorn
from typing import Optional
from pydantic import BaseModel, Field
from a2a.types import AgentCard
from google.adk.agents import Agent
from google.adk.planners import PlanReActPlanner
from google.adk.a2a.utils.agent_to_a2a import to_a2a

from src.a2a_services.base import build_llm_client
from src.config.settings import a2a_service_config


class ConsultantInput(BaseModel):
    query: str = Field(..., description="Câu hỏi gốc của khách hàng")
    analysis: str = Field(..., description="Kết quả phân tích từ analysis agent (JSON string)")
    inventory: Optional[str] = Field(None, description="Thông tin tồn kho từ inventory agent (JSON string, optional)")
    order: Optional[str] = Field(None, description="Thông tin đơn hàng từ order agent (JSON string, optional)")
    coordinator_summary: Optional[str] = Field(None, description="Tóm tắt từ coordinator về luồng xử lý (optional)")

class ConsultantOutput(BaseModel):
    response: str = Field(..., description="Câu trả lời tự nhiên bằng tiếng Việt cho khách hàng")


planner = PlanReActPlanner()
consultant_agent = Agent(
    name="consultant_agent",
    model=build_llm_client(),
    description="Tạo câu trả lời tự nhiên cho khách hàng dựa trên kết quả từ các agent khác",
    instruction="""Bạn là Consultant Agent - tư vấn viên.

NHIỆM VỤ:
- Tổng hợp thông tin từ inventory agent (giá, tồn kho) và order agent (order ID, trạng thái đơn)
- Tạo câu trả lời hoàn chỉnh, thân thiện bằng tiếng Việt

YÊU CẦU:
- Trả lời trực tiếp, không đưa mã nguồn hay pseudo-code
- Dùng giọng điệu tự nhiên, tích cực; liệt kê rõ ràng thông tin sản phẩm và trạng thái đơn hàng
- Nếu thiếu dữ liệu, giải thích ngắn gọn và đề xuất bước tiếp theo cho khách
    """,
    planner=planner,
    input_schema=ConsultantInput,
    output_schema=ConsultantOutput
)

# Define Agent card according to A2A protocol
consultant_card = AgentCard(
    name="consultant_agent",
    url=a2a_service_config.build_agent_base(a2a_service_config.consultant_port),
    description="Tạo câu trả lời tự nhiên cho khách hàng từ thông tin tổng hợp",
    version="1.0.0",
    capabilities={
        "intents": ["generate_response", "summarize_info", "format_natural_language"]
    },
    skills=[],
    defaultInputModes=["application/json"],
    defaultOutputModes=["text/plain"],
    supportsAuthenticatedExtendedCard=False,
)

a2a_app = to_a2a(consultant_agent, port=a2a_service_config.consultant_port, agent_card=consultant_card)
app = a2a_app


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=a2a_service_config.consultant_port,
        log_level="info",
    )

"""
python -m src.a2a_services.consultant_agent
"""
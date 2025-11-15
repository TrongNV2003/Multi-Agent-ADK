from __future__ import annotations

import json
from typing import Any, Dict, Optional

import uvicorn
from pydantic import BaseModel, Field
from a2a.types import AgentCard
from google.adk.agents import Agent
from google.adk.planners import PlanReActPlanner
from google.adk.a2a.utils.agent_to_a2a import to_a2a

from src.a2a_services.base import build_llm_client
from src.config.settings import a2a_service_config
from src.tools.get_products import check_inventory_detail


class InventoryInput(BaseModel):
    query: str = Field(..., description="Thông tin sản phẩm cần check (bao gồm tên, dung lượng, màu)")
    context: Optional[str] = Field(None, description="Context từ analysis agent (JSON string, optional)")

class InventoryOutput(BaseModel):
    product_name: str = Field(..., description="Tên sản phẩm (không bao gồm dung lượng và màu sắc)")
    storage: str = Field(..., description="Dung lượng lưu trữ (ví dụ: 256GB, 512GB) hoặc chuỗi rỗng")
    color: str = Field(..., description="Màu sắc sản phẩm hoặc chuỗi rỗng")


def fetch_inventory_data(product: str, storage: str = "", color: str = "") -> Dict[str, Any]:
    """Invoke MCP inventory tool and return parsed JSON."""
    raw_result = check_inventory_detail(product, storage, color)
    try:
        return json.loads(raw_result)
    except json.JSONDecodeError:
        return {"raw": raw_result}


planner = PlanReActPlanner()
inventory_agent = Agent(
    name="inventory_agent",
    model=build_llm_client(),
    description="Trích xuất thông tin sản phẩm để kiểm tra tồn kho",
    instruction="""Bạn là Inventory Param Extractor - trích xuất thông tin sản phẩm.

NHIỆM VỤ:
Phân tích query để trích xuất 3 thông tin RIÊNG BIỆT:
- product_name: TÊN SẢN PHẨM (ví dụ: "iPhone 15 Pro Max", KHÔNG bao gồm dung lượng/màu)
- storage: DUNG LƯỢNG (ví dụ: "256GB", "512GB", hoặc "" nếu không có)
- color: MÀU SẮC (ví dụ: "Titan tự nhiên", "Đen", hoặc "" nếu không có)

VÍ DỤ:
Input: "iPhone 15 Pro Max 256GB màu Titan tự nhiên"
Output:
{
  "product_name": "iPhone 15 Pro Max",
  "storage": "256GB",
  "color": "Titan tự nhiên"
}

Input: "iPad Air màu Xanh"
Output:
{
  "product_name": "iPad Air",
  "storage": "",
  "color": "Xanh"
}

YÊU CẦU:
- PHẢI trả về JSON thuần, KHÔNG markdown, KHÔNG giải thích
- Chỉ trả 3 khóa: product_name, storage, color
- Nếu không tìm thấy thông tin nào, điền chuỗi rỗng ""
- KHÔNG thêm /*PLANNING*/ hay bất kỳ text nào khác
    """,
    tools=[fetch_inventory_data],
    planner=planner,
    input_schema=InventoryInput,
    output_schema=InventoryOutput
)

# Define Agent card according to A2A protocol
inventory_card = AgentCard(
    name="inventory_agent",
    url=a2a_service_config.build_agent_base(a2a_service_config.inventory_port),
    description="Kiểm tra tồn kho và giá sản phẩm từ database qua MCP",
    version="1.0.0",
    capabilities={
        "intents": ["check_inventory", "get_product_price", "query_stock_quantity"]
    },
    skills=[],
    defaultInputModes=["text/plain", "application/json"],
    defaultOutputModes=["application/json"],
    supportsAuthenticatedExtendedCard=False,
)

a2a_app = to_a2a(inventory_agent, port=a2a_service_config.inventory_port, agent_card=inventory_card)
app = a2a_app


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=a2a_service_config.inventory_port,
        log_level="info",
    )

"""
python -m src.a2a_services.inventory_agent
"""
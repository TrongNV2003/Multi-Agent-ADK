from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

import uvicorn
from pydantic import BaseModel, Field
from a2a.types import AgentCard
from google.adk.agents import Agent
from google.adk.planners import PlanReActPlanner
from google.adk.a2a.utils.agent_to_a2a import to_a2a

from src.a2a_services.base import build_llm_client
from src.config.settings import a2a_service_config
from src.tools.create_order import create_customer_order


class OrderInput(BaseModel):
    query: str = Field(..., description="Yêu cầu tạo đơn hàng từ khách hàng")
    inventory_info: str = Field(..., description="Thông tin tồn kho từ inventory agent (JSON string)")
    customer_info: str = Field(..., description="Thông tin khách hàng bao gồm tên, số điện thoại, địa chỉ (JSON string)")

class OrderParams(BaseModel):
    product: str = Field(..., description="Tên sản phẩm")
    color: str = Field(..., description="Màu sắc")
    storage: str = Field(..., description="Dung lượng")
    quantity: int = Field(..., description="Số lượng")
    price: float = Field(..., description="Giá sản phẩm")
    customer_name: str = Field(..., description="Tên khách hàng")
    customer_phone: str = Field(..., description="Số điện thoại khách hàng")
    customer_address: Optional[str] = Field(None, description="Địa chỉ khách hàng")


def submit_order(order_details: Dict[str, Any]) -> Dict[str, Any]:
    """Create an order via MCP and normalize the response."""
    payload = order_details or {}
    payload.setdefault("order_id", f"order_{uuid.uuid4().hex[:8]}")
    raw_result = create_customer_order(payload)
    normalized: Dict[str, Any]
    try:
        normalized = json.loads(raw_result)
    except (TypeError, json.JSONDecodeError):
        normalized = {"message": raw_result}

    success = False
    if isinstance(raw_result, str):
        success = "success" in raw_result.lower()
    elif isinstance(normalized, dict):
        success = str(normalized.get("status", "")).lower() == "success"

    normalized.setdefault("status", "success" if success else "error")
    normalized["order_payload"] = payload
    normalized["raw"] = raw_result
    return normalized


class OrderOutput(BaseModel):
    order_ready: bool = Field(..., description="True nếu đủ thông tin để tạo đơn hàng")
    order_params: OrderParams = Field(..., description="Thông tin đơn hàng đầy đủ")


planner = PlanReActPlanner()
order_agent = Agent(
    name="order_agent",
    model=build_llm_client(),
    description="Tạo và quản lý đơn hàng cho khách",
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
    tools=[submit_order],
    planner=planner,
    input_schema=OrderInput,
    output_schema=OrderOutput
)

# Define Agent card according to A2A protocol
order_card = AgentCard(
    name="order_agent",
    url=a2a_service_config.build_agent_base(a2a_service_config.order_port),
    description="Tạo và quản lý đơn hàng cho khách hàng thông qua MCP",
    version="1.0.0",
    capabilities={
        "intents": ["create_order", "manage_order", "generate_order_id"]
    },
    skills=[],
    defaultInputModes=["application/json"],
    defaultOutputModes=["application/json"],
    supportsAuthenticatedExtendedCard=False,
)

a2a_app = to_a2a(order_agent, port=a2a_service_config.order_port, agent_card=order_card)
app = a2a_app


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=a2a_service_config.order_port,
        log_level="info",
    )

"""
python -m src.a2a_services.order_agent
"""
import re
import json
import uuid
from typing import Any, Dict

from loguru import logger
from google.genai import types

from src.tools.get_products import get_product_info_async
from src.tools.create_order import create_order_async


async def _invoke_remote_agent(
    runner,
    session_prefix: str,
    payload: str,
    user_id: str,
) -> str:
    """Send payload to a remote A2A agent via its runner."""
    session = await runner.session_service.create_session(
        app_name=runner.app_name,
        user_id=user_id,
        session_id=f"{session_prefix}-{uuid.uuid4()}",
    )

    message = types.Content(role="user", parts=[types.Part(text=payload)])
    final_response = ""
    async for event in runner.run_async(
        user_id=session.user_id,
        session_id=session.id,
        new_message=message,
    ):
        if getattr(event, "is_final_response", False):
            if event.content and event.content.parts:
                final_response = event.content.parts[0].text or ""
            break

    return final_response


def _json_load(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}
    return {"raw": raw}


async def handle_inventory_agent_call(
    query: str,
    context: str,
    runner,
    agent_instance=None,
) -> str:
    """
    1. Send request to remote Inventory Agent to parse product info
    2. Extract params from agent response
    3. Call MCP tool get_product_info_async with those params
    4. Return formatted result
    """
    _ = agent_instance
    context_data = _json_load(context)
    
    # Step 1: Ask Inventory Agent to extract product info
    payload = json.dumps(
        {
            "query": query,
            "analysis_context": context_data,
        },
        ensure_ascii=False,
    )
    agent_response = await _invoke_remote_agent(
        runner=runner,
        session_prefix="inventory",
        payload=payload,
        user_id="inventory_agent",
    )
    logger.debug(f"Inventory Agent response: {agent_response}")
    
    # Step 2: Parse agent response to get params
    try:
        response_data = _json_load(agent_response)
        if not isinstance(response_data, dict):
            json_match = re.search(r'\{.*\}', agent_response, re.DOTALL)
            if json_match:
                response_data = json.loads(json_match.group())
            else:
                response_data = {}
        
        product = response_data.get("product_name") or response_data.get("product", "")
        storage = response_data.get("storage", "")
        color = response_data.get("color", "")
        
        if not product:
            product = context_data.get("product_details") or query
            
    except Exception as e:
        logger.warning(f"[A2A] Failed to parse agent response: {e}")
        product = context_data.get("product_details") or query
        storage = ""
        color = ""
    
    # Step 3: Call MCP tool
    try:
        mcp_result = await get_product_info_async(
            product=product,
            storage=storage,
            color=color
        )
        logger.debug(f"[A2A] MCP tool result: {mcp_result}")
        
        mcp_data = _json_load(mcp_result)
        
        if isinstance(mcp_data, dict):
            products = mcp_data.get("products", [])
            if products and isinstance(products, list) and len(products) > 0:
                product_info = products[0]
                result = {
                    "product_name": product_info.get("product", product),
                    "storage": product_info.get("storage", storage),
                    "color": product_info.get("color", color),
                    "stock_status": "in_stock" if product_info.get("quantity", 0) > 0 else "out_of_stock",
                    "price": product_info.get("price", 0),
                    "quantity": product_info.get("quantity", 0),
                }
            else:
                result = {
                    "product_name": product,
                    "storage": storage,
                    "color": color,
                    "stock_status": "unknown",
                    "price": 0,
                    "quantity": 0,
                    "error": "Product not found",
                }
        else:
            result = {
                "product_name": product,
                "storage": storage,
                "color": color,
                "stock_status": "error",
                "error": "Invalid MCP response",
            }
            
    except Exception as e:
        logger.error(f"[A2A] MCP tool error: {e}")
        result = {
            "product_name": product,
            "storage": storage,
            "color": color,
            "stock_status": "error",
            "error": str(e),
        }
    
    logger.debug(f"Inventory Agent response: {json.dumps(result, ensure_ascii=False)}")
    return json.dumps(result, ensure_ascii=False)


async def handle_order_agent_call(
    query: str,
    inventory_info: str,
    customer_info: str,
    runner,
    agent_instance=None,
) -> str:
    """
    1. Send request to remote Order Agent to prepare order params
    2. Extract order details from agent response
    3. Call MCP tool create_order_async with those details
    4. Return formatted result
    """
    _ = agent_instance
    inventory_data = _json_load(inventory_info)
    customer_data = _json_load(customer_info)
    
    # Step 1: Ask remote agent to prepare order
    payload = json.dumps(
        {
            "customer_query": query,
            "inventory_result": inventory_data,
            "customer_info": customer_data,
        },
        ensure_ascii=False,
    )
    agent_response = await _invoke_remote_agent(
        runner=runner,
        session_prefix="order",
        payload=payload,
        user_id="order_agent",
    )
    logger.debug(f"[A2A] Order Agent response: {agent_response}")
    
    # Step 2: Parse agent response to get order params
    try:
        response_data = _json_load(agent_response)
        if not isinstance(response_data, dict):
            json_match = re.search(r'\{.*\}', agent_response, re.DOTALL)
            if json_match:
                response_data = json.loads(json_match.group())
            else:
                response_data = {}
        
        # Build order payload for MCP
        order_payload = {
            "product": inventory_data.get("product_name") or response_data.get("product", ""),
            "color": inventory_data.get("color") or response_data.get("color", ""),
            "storage": inventory_data.get("storage") or response_data.get("storage", ""),
            "quantity": response_data.get("quantity", 1),
            "total_price": inventory_data.get("price", 0) * response_data.get("quantity", 1),
            "customer_info": {
                "customer_name": customer_data.get("customer_name", ""),
                "conversation_id": customer_data.get("conversation_id", f"conv_{uuid.uuid4().hex[:6]}"),
            }
        }
        
        # Validate required fields
        if not order_payload["product"] or order_payload["total_price"] == 0:
            return json.dumps({
                "order_created": False,
                "error": "Missing product or price information",
                "message": "Không thể tạo đơn hàng do thiếu thông tin sản phẩm hoặc giá",
            }, ensure_ascii=False)
            
    except Exception as e:
        logger.error(f"[A2A] Failed to parse order params: {e}")
        return json.dumps({
            "order_created": False,
            "error": str(e),
            "message": "Lỗi khi xử lý thông tin đơn hàng",
        }, ensure_ascii=False)
    
    # Step 3: Call actual MCP tool
    try:
        mcp_result = await create_order_async(order_payload)
        logger.debug(f"[A2A] MCP tool result: {mcp_result}")
        
        order_id = "unknown"
        if isinstance(mcp_result, str) and "order_" in mcp_result:
            import re
            match = re.search(r'order_([a-f0-9]+)_', mcp_result)
            if match:
                order_id = f"order_{match.group(1)}"
        
        success = isinstance(mcp_result, str) and "success" in mcp_result.lower()
        
        result = {
            "order_created": success,
            "order_details": {
                "order_id": order_id,
                "product": order_payload["product"],
                "color": order_payload["color"],
                "storage": order_payload["storage"],
                "quantity": order_payload["quantity"],
                "total_price": order_payload["total_price"],
            },
            "customer_info": order_payload["customer_info"],
            "message": mcp_result if isinstance(mcp_result, str) else "Đơn hàng đã được tạo",
        }
        
    except Exception as e:
        logger.error(f"[A2A] MCP tool error: {e}")
        result = {
            "order_created": False,
            "error": str(e),
            "message": f"Lỗi khi tạo đơn hàng: {str(e)}",
        }
    
    logger.debug(f"[A2A] Order Agent response: order_created={result.get('order_created')}")
    return json.dumps(result, ensure_ascii=False)

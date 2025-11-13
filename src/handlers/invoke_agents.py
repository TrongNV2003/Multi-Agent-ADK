import uuid
import json
from loguru import logger
from typing import Dict, Any
from google.genai import types
from textwrap import dedent

from src.tools.create_order import create_order_async
from src.tools.get_products import get_product_info_async


async def handle_inventory_agent_call(
    query: str,
    context: str,
    runner,
    agent_instance
) -> str:
    """Invoke the Inventory Agent via its runner and execute the MCP tool."""
    _ = agent_instance  # Agent instance kept for parity or future use

    try:
        context_data = json.loads(context) if context else {}
    except Exception:
        context_data = {}

    logger.info(f"[A2A] → Inventory Agent: {query}")

    prompt = dedent(f"""
        Bạn là Inventory Agent. Hãy trích xuất thông tin sản phẩm cần kiểm tra tồn kho.

        INPUT:
        - Customer query: "{query}"
        - Context (JSON): {json.dumps(context_data, ensure_ascii=False)}

        OUTPUT:
        Trả về JSON thuần với định dạng:
        {{
          "query_needed": "check_inventory_detail",
          "query_params": {{
            "product": "...",
            "storage": "...",
            "color": "..."
          }}
        }}

        YÊU CẦU:
        - Chỉ trả JSON hợp lệ, không giải thích thêm.
        - Nếu thiếu thông tin, điền chuỗi rỗng.
    """)

    session = await runner.session_service.create_session(
        app_name=runner.app_name,
        user_id="inventory_agent",
        session_id=f"inventory-{uuid.uuid4()}"
    )

    message = types.Content(role="user", parts=[types.Part(text=prompt)])
    llm_response = ""
    last_function_call = None
    async for event in runner.run_async(
        user_id=session.user_id,
        session_id=session.id,
        new_message=message
    ):
        if getattr(event, "function_call", None):
            last_function_call = event.function_call
        if getattr(event, "is_final_response", False):
            if event.content and event.content.parts:
                llm_response = event.content.parts[0].text
            break

    def _extract_json(text: str) -> Dict[str, Any]:
        decoder = json.JSONDecoder()
        stripped = text.strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            start = stripped.find("{")
            while start != -1:
                try:
                    obj, _ = decoder.raw_decode(stripped, start)
                    return obj
                except json.JSONDecodeError:
                    start = stripped.find("{", start + 1)
            raise

    used_inventory_fallback = False
    try:
        parsed = _extract_json(llm_response) if llm_response.strip() else {}
        params = parsed.get("query_params", {}) if parsed else {}
        if not params and last_function_call:
            try:
                call_args = last_function_call.args
                params = json.loads(call_args) if isinstance(call_args, str) else call_args
            except Exception as call_exc:
                logger.debug(f"[A2A] Inventory function call args parse error: {call_exc}")
    except Exception as exc:
        parsed = {}
        params = {}
        logger.debug(f"[A2A] Inventory JSON parse error: {exc}")

    if not params:
        used_inventory_fallback = True
        logger.warning("[A2A] Inventory agent missing structured params, using fallback")
        fallback_product = context_data.get("product_details") or query
        params = {
            "product": fallback_product,
            "storage": context_data.get("storage", ""),
            "color": context_data.get("color", "")
        }

    def _safe_load_json(raw):
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw}
        return {"raw": raw}

    try:

        tool_raw = await get_product_info_async(
            product=params.get("product", ""),
            storage=params.get("storage", ""),
            color=params.get("color", "")
        )
        tool_data = _safe_load_json(tool_raw)
        products = tool_data.get("products") if isinstance(tool_data, dict) else None
        product_info = products[0] if isinstance(products, list) and products else {}

        payload = {
            "product_name": product_info.get("product") or params.get("product", ""),
            "storage": product_info.get("storage") or params.get("storage", ""),
            "color": product_info.get("color") or params.get("color", ""),
            "stock_status": "in_stock" if product_info and product_info.get("quantity", 0) > 0 else tool_data.get("status", "unknown"),
            "price": product_info.get("price", 0),
            "quantity": product_info.get("quantity", 0),
            "raw_tool_result": tool_data,
            "fallback_used": used_inventory_fallback
        }
    except Exception as exc:
        logger.error(f"[A2A] Error calling inventory MCP tool: {exc}")
        payload = {
            "error": str(exc),
            "stock_status": "error",
            "raw_output": llm_response,
            "fallback_used": used_inventory_fallback
        }

    result = json.dumps(payload, ensure_ascii=False)
    logger.info(f"[A2A] Inventory Agent →: {result}")
    return result


async def handle_order_agent_call(
    query: str,
    inventory_info: str,
    customer_info: str,
    runner,
    agent_instance
) -> str:
    """Invoke Order Agent and execute MCP order creation."""
    _ = agent_instance  # Agent instance kept for parity or future use

    try:
        inv_data = json.loads(inventory_info) if inventory_info else {}
    except Exception:
        inv_data = {}

    try:
        cust_data = json.loads(customer_info) if customer_info else {}
    except Exception:
        cust_data = {}

    logger.info("[A2A] → Order Agent")

    prompt = dedent(f"""
        Bạn là Order Agent. Hãy chuẩn bị dữ liệu tạo đơn hàng dựa trên thông tin sau.

        CUSTOMER QUERY: "{query}"
        INVENTORY RESULT (JSON): {json.dumps(inv_data, ensure_ascii=False)}
        CUSTOMER INFO (JSON): {json.dumps(cust_data, ensure_ascii=False)}

        OUTPUT:
        Trả về JSON thuần với format:
        {{
          "order_ready": true/false,
          "order_params": {{
            "product": "...",
            "color": "...",
            "storage": "...",
            "quantity": number,
            "price": number,
            "customer_name": "...",
            "customer_phone": "...",
            "customer_address": "..."
          }}
        }}

        YÊU CẦU:
        - Chỉ trả JSON hợp lệ.
        - Giữ nguyên thông tin màu sắc, dung lượng.
        - quantity mặc định là 1 nếu không có.
    """)

    session = await runner.session_service.create_session(
        app_name=runner.app_name,
        user_id="order_agent",
        session_id=f"order-{uuid.uuid4()}"
    )

    message = types.Content(role="user", parts=[types.Part(text=prompt)])
    llm_response = ""
    last_function_call = None
    async for event in runner.run_async(
        user_id=session.user_id,
        session_id=session.id,
        new_message=message
    ):
        if getattr(event, "function_call", None):
            last_function_call = event.function_call
        if getattr(event, "is_final_response", False):
            if event.content and event.content.parts:
                llm_response = event.content.parts[0].text
            break

    def _extract_json(text: str) -> Dict[str, Any]:
        decoder = json.JSONDecoder()
        stripped = text.strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            start = stripped.find("{")
            while start != -1:
                try:
                    obj, _ = decoder.raw_decode(stripped, start)
                    return obj
                except json.JSONDecodeError:
                    start = stripped.find("{", start + 1)
            raise

    used_order_fallback = False
    parsed = {}
    try:
        if llm_response.strip():
            parsed = _extract_json(llm_response)
        elif last_function_call:
            call_args = last_function_call.args
            parsed = json.loads(call_args) if isinstance(call_args, str) else call_args
            if last_function_call.name and "create_customer_order" in last_function_call.name:
                parsed = {
                    "order_ready": True,
                    "order_params": parsed.get("order_details", parsed)
                }
    except Exception as exc:
        logger.debug(f"[A2A] Order agent parse attempt failed: {exc}")

    if not isinstance(parsed, dict):
        parsed = {}

    if not parsed.get("order_params"):
        used_order_fallback = True
        logger.warning("[A2A] Order agent missing structured params, using fallback")
        parsed = {
            "order_ready": True,
            "order_params": {
                "product": inv_data.get("product_name") or query,
                "color": inv_data.get("color", ""),
                "storage": inv_data.get("storage", ""),
                "quantity": inv_data.get("quantity", 1) or 1,
                "price": inv_data.get("price", 0),
                "customer_name": cust_data.get("customer_name", "Khách hàng"),
                "customer_phone": cust_data.get("customer_phone", ""),
                "customer_address": cust_data.get("customer_address", ""),
                "message": "Đơn hàng được tạo dựa trên thông tin tồn kho."
            }
        }

    params = parsed.get("order_params", {})

    def _safe_load_json(raw):
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw}
        return {"raw": raw}

    try:

        quantity = params.get("quantity", 1) or 1
        try:
            quantity = int(quantity)
        except (ValueError, TypeError):
            quantity = 1

        price = params.get("price")
        if price is None:
            price = inv_data.get("price") or inv_data.get("raw_tool_result", {}).get("price") if isinstance(inv_data.get("raw_tool_result"), dict) else None
        price = price or 0
        try:
            price = float(price)
        except (ValueError, TypeError):
            price = 0

        order_payload = {
            "order_id": params.get("order_id") or f"order_{uuid.uuid4().hex[:8]}",
            "product": params.get("product") or inv_data.get("product_name", ""),
            "color": params.get("color") or inv_data.get("color", ""),
            "storage": params.get("storage") or inv_data.get("storage", ""),
            "quantity": quantity,
            "total_price": price * quantity,
            "customer_info": {
                "customer_name": params.get("customer_name") or cust_data.get("customer_name", "Khách hàng"),
                "conversation_id": cust_data.get("conversation_id") or params.get("conversation_id", f"conv_{uuid.uuid4().hex[:6]}")
            },
            "message": params.get("message") or "Đơn hàng đã được tạo."
        }

        order_raw = await create_order_async(order_payload)
        order_data = _safe_load_json(order_raw)
        success = isinstance(order_raw, str) and "success" in order_raw.lower()

        payload = {
            "order_created": success,
            "order_details": {
                "order_id": order_payload["order_id"],
                "product": order_payload["product"],
                "color": order_payload["color"],
                "storage": order_payload["storage"],
                "quantity": order_payload["quantity"],
                "total_price": order_payload["total_price"]
            },
            "customer_info": order_payload["customer_info"],
            "message": order_raw if isinstance(order_raw, str) else json.dumps(order_raw, ensure_ascii=False),
            "raw_tool_result": order_data,
            "fallback_used": used_order_fallback
        }
    except Exception as exc:
        logger.error(f"[A2A] Error calling order MCP tool: {exc}")
        payload = {
            "order_created": False,
            "error": str(exc),
            "raw_output": llm_response,
            "fallback_used": True
        }

    result = json.dumps(payload, ensure_ascii=False)
    logger.info(f"[A2A] Order Agent →: {result[:150]}...")
    return result

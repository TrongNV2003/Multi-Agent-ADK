import json
import asyncio
from loguru import logger
from typing import Dict, Any
from mcp import ClientSession
from mcp.client.sse import sse_client


async def create_order_async(
    order_details: Dict[str, Any],
    max_retries: int = 3,
    timeout: int = 15
) -> str:
    """Create order via MCP server with retry logic."""
    last_error = None
    
    for attempt in range(max_retries):
        try:
            logger.debug(f"Attempt {attempt + 1}/{max_retries} to create order")
            logger.debug(f"Order details: {order_details}")
            
            async with sse_client(url="http://localhost:8000/sse") as (read, write):
                async with ClientSession(read, write) as session:
                    await asyncio.wait_for(session.initialize(), timeout=timeout)
                    logger.debug(f"MCP session initialized")
                    
                    result = await asyncio.wait_for(
                        session.call_tool("create_order", {"order_details": order_details}),
                        timeout=timeout
                    )
                    
                    result_text = None
                    if result and hasattr(result, 'content') and result.content:
                        for content in result.content:
                            if hasattr(content, 'text'):
                                result_text = content.text
                                break
                    elif isinstance(result, str):
                        result_text = result
                    else:
                        result_text = str(result)
                    
                    if result_text:
                        if "successfully" in result_text.lower() or "success" in result_text.lower():
                            logger.info(f"Successfully created order on attempt {attempt + 1}")
                        elif "error" in result_text.lower():
                            logger.error(f"Server returned error: {result_text}")
                        return result_text
                    else:
                        raise ValueError("Empty response from server")
                        
        except asyncio.TimeoutError:
            last_error = f"Timeout after {timeout}s"
            logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries}")
        except ConnectionError as e:
            last_error = f"Connection error: {str(e)}"
            logger.warning(f"Connection error on attempt {attempt + 1}/{max_retries}: {e}")
        except Exception as e:
            last_error = str(e)
            logger.error(f"Error on attempt {attempt + 1}/{max_retries}: {e}", exc_info=True)
        
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt
            logger.debug(f"Waiting {wait_time}s before retry...")
            await asyncio.sleep(wait_time)
    
    error_msg = f"Failed to create order after {max_retries} attempts. Last error: {last_error}"
    logger.error(f"{error_msg}")
    return f"Error: {error_msg}"


def create_order(order_details: Dict[str, Any]) -> str:
    """Synchronous wrapper for create_order_async."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, create_order_async(order_details))
                return future.result()
        else:
            return loop.run_until_complete(create_order_async(order_details))
    except RuntimeError:
        return asyncio.run(create_order_async(order_details))

def create_customer_order(order_details: Dict[str, Any]) -> str:
    """
    Create a customer order with the given details.
    
    Args:
        order_details: Order information dict with fields:
            - order_id: Unique order ID (will be generated if not provided)
            - product: Product name
            - storage: Storage capacity
            - color: Color variant
            - quantity: Order quantity
            - total_price: Total price
            - customer_info: Dict with customer_name and conversation_id
            - message: Optional message
            
    Returns:
        Success message with order file path or error message
    """
    try:
        payload = order_details
        if isinstance(order_details, str):
            try:
                payload = json.loads(order_details)
            except json.JSONDecodeError as parse_error:
                logger.error(f"Failed to parse order_details string: {parse_error}")
                return f"Error: Invalid JSON string - {parse_error}"
        
        logger.debug(f"Calling MCP create_order with: {payload}")
        
        result = create_order(payload)
        
        logger.debug(f"MCP create_order result: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in create_customer_order: {e}", exc_info=True)
        return f"Error: Failed to create order - {str(e)}"
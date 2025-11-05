import json
import asyncio
from typing import Optional
from loguru import logger
from mcp import ClientSession
from mcp.client.sse import sse_client


async def get_product_info_async(
    product: str, 
    storage: Optional[str] = None, 
    color: Optional[str] = None, 
    max_retries: int = 3, 
    timeout: int = 15
) -> str:
    last_error = None
    
    for attempt in range(max_retries):
        try:
            logger.debug(f"Attempt {attempt + 1}/{max_retries} to get product info")
            
            kwargs = {"product": product}
            if storage:
                kwargs["storage"] = storage
            if color:
                kwargs["color"] = color
            
            async with sse_client(url="http://localhost:8000/sse") as (read, write):
                async with ClientSession(read, write) as session:
                    await asyncio.wait_for(session.initialize(), timeout=timeout)
                    logger.debug(f"MCP session initialized")
                    
                    result = await asyncio.wait_for(
                        session.call_tool("get_product_info", kwargs),
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
                        logger.info(f"Successfully retrieved product info on attempt {attempt + 1}")
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
    
    error_msg = f"Failed to get product info after {max_retries} attempts. Last error: {last_error}"
    logger.error(f"{error_msg}")
    return json.dumps({"status": "error", "message": error_msg}, ensure_ascii=False)


def get_product_info(product: str, storage: Optional[str] = None, color: Optional[str] = None) -> str:
    """Synchronous wrapper for get_product_info_async."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, get_product_info_async(product, storage, color))
                return future.result()
        else:
            return loop.run_until_complete(get_product_info_async(product, storage, color))
    except RuntimeError:
        return asyncio.run(get_product_info_async(product, storage, color))


def check_inventory_detail(product: str, storage: str, color: str) -> str:
    """
    Check product inventory and pricing details.
    
    Args:
        product: Product name (e.g., 'iPhone 15 Pro Max')  
        storage: Storage capacity (e.g., '256GB' or empty string '')
        color: Color variant (e.g., 'Titan tự nhiên' or empty string '')
        
    Returns:
        JSON string with product details or error message
    """
    try:
        logger.debug(f"Calling MCP get_product_info: product={product}, storage={storage}, color={color}")
        
        result = get_product_info(
            product=product, 
            storage=storage if storage and storage.strip() else None, 
            color=color if color and color.strip() else None
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error in check_inventory_detail: {e}", exc_info=True)
        return json.dumps({
            "status": "error",
            "message": f"Failed to check inventory: {str(e)}"
        }, ensure_ascii=False)
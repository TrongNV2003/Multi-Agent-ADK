import os
import uuid
import json
import signal
from loguru import logger
from typing import Optional
from mcp.server.fastmcp import FastMCP

from src.db.connector import MongoDBClient


mcp = FastMCP("mcp server")


db_client = None

def check_mongodb_connection(timeout: int = 5):
    class TimeoutException(Exception):
        pass

    def timeout_handler(signum, frame):
        raise TimeoutException("Kết nối MongoDB timeout!")

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)

    try:
        client = MongoDBClient()
        client.get_client().admin.command('ping')
        logger.info("MongoDB connected successfully!")
        signal.alarm(0)
        return client
    except TimeoutException:
        logger.error("Remember to start mongodb server before running this MCP server:")
        logger.error("   sudo systemctl start mongod")
        signal.alarm(0)
        return None
    except Exception as e:
        logger.error(f"Error connecting to MongoDB: {str(e)}")
        logger.error("Remember to start mongodb server before running this MCP server:")
        logger.error("   sudo systemctl start mongod")
        signal.alarm(0)
        return None
    finally:
        signal.alarm(0)

db_client = check_mongodb_connection(timeout=5)

if db_client is None:
    logger.critical("MCP server cannot start due to missing MongoDB")
    exit(1)


@mcp.tool(name="create_order")
def create_order(order_details: dict) -> str:
    """
    Saves the given order data (dictionary) to a file in the 'orders' subdirectory, with a standardized format.
    Returns a success message with the filename or an error message.
    """
    try:
        orders_dir = "orders"
        if not os.path.exists(orders_dir):
            os.makedirs(orders_dir)
            
        input_data = order_details

        if not isinstance(input_data, dict):
            return f"Error: Input data is not a valid dictionary, received: {type(input_data)}"

        if "order_details" in input_data:
            input_data = input_data["order_details"]

        required_fields = ["product", "color", "storage", "quantity", "total_price", "customer_info"]
        missing_fields = [field for field in required_fields if field not in input_data]
        if missing_fields:
            return f"Error: Missing required fields: {', '.join(missing_fields)}"        

        order_id = f"order_{uuid.uuid4().hex[:16]}"
        
        standard_order = {
            "order_details": {
                "order_id": order_id,
                "product": input_data.get("product", "Unknown Product"),
                "color": input_data.get("color", "Unknown Color"),
                "storage": input_data.get("storage", "Unknown Storage"),
                "quantity": input_data.get("quantity", 1),
                "total_price": input_data.get("total_price", 0),
                "customer_info": {
                    "customer_name": input_data.get("customer_info", {}).get("customer_name", "Guest"),
                    "conversation_id": input_data.get("customer_info", {}).get("conversation_id", f"{uuid.uuid4()}")
                }
            },
            "message": input_data.get("message", "Đơn hàng đã được tạo.")
        }

        order_id = standard_order["order_details"]["order_id"]
        conversation_id = standard_order["order_details"]["customer_info"]["conversation_id"]

        filename_base = f"{order_id}_{conversation_id}"
        filename = f"{filename_base}.json"
        filepath = os.path.join(orders_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(standard_order, f, ensure_ascii=False, indent=4)

        return f"Order data successfully saved to file: {filepath}"
    except Exception as e:
        return f"Error saving order to file: {str(e)}"

@mcp.tool(name="get_order")
def get_order(order_id: str) -> dict:
    """
    Retrieves the content of an order file by its order_id.
    Returns a dictionary with file_content or error message.
    """
    try:
        orders_dir = "orders"
        for filename in os.listdir(orders_dir):
            if filename.startswith(f"order_{order_id}") and filename.endswith(".json"):
                file_path = os.path.join(orders_dir, filename)
                with open(file_path, "r", encoding="utf-8") as f:
                    file_content = f.read()
                return {"file_content": file_content}

        return {"error": f"Order file with ID {order_id} not found", "status": 404}
    except Exception as e:
        return {"error": f"Error retrieving order file: {str(e)}", "status": 500}


@mcp.tool(name="get_product_info")
def get_product_info(product: str, storage: Optional[str] = None, color: Optional[str] = None) -> str:
    """
    Retrieves inventory details from storage based on the product. 
    Input is a JSON string or object with product name, and optionally storage and color.
    """
    try:
        if db_client is None:
            logger.error("MongoDB client not initialized")
            return json.dumps({"error": "Cannot connect to MongoDB database", "status": "error"})

        matching_products = db_client.get_products(
            product_name=product,
            storage=storage,
            color=color
        )

        if not matching_products:
            logger.warning(f"No product found for: {product}")
            return json.dumps({
                "error": f"No product found matching product='{product}', "
                            f"storage='{storage or 'any'}', color='{color or 'any'}'",
                            "status": "not_found"
                })

        result = {
            "status": "success",
            "products": matching_products
        }
        logger.debug(f"Found products: {result}")
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Error retrieving product info: {str(e)}")
        return json.dumps({
            "error": f"Error retrieving product info: {str(e)}",
            "status": "error"
        }, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    logger.info("Starting MCP server...")
    mcp.run(transport="sse")
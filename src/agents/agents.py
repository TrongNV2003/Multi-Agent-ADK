from google.genai import types
from google.adk.agents import Agent
from google.adk.planners import BuiltInPlanner


class AnalysisAgent:
    def __init__(self, client):
        self.planner = BuiltInPlanner(
            thinking_config=types.ThinkingConfig(
                include_thoughts=True,
                thinking_budget=1024,
            )
        )
        self.agent = Agent(
            name="analysis_agent",
            model=client,
            description="Trả lời câu hỏi khách hàng và cung cấp thông tin sản phẩm",
            instruction="""Phân tích kỹ lưỡng yêu cầu của khách hàng:
Xác định các thông tin quan trọng như:
1. Tên sản phẩm hoặc loại sản phẩm khách hàng quan tâm.
2. Ý định chính của khách hàng (ví dụ: hỏi thông tin, kiểm tra tồn kho, hỏi giá, muốn đặt hàng).
3. Bất kỳ chi tiết cụ thể nào khác (optional) (màu sắc, dung lượng, v.v.).

Dựa trên phân tích, hãy chuẩn bị một bản tóm tắt rõ ràng dạng JSON với các trường:
- product_details: (string) mô tả sản phẩm khách quan tâm
- customer_intent: (string) một trong: 'check_inventory_price', 'place_order', 'general_query', 'product_info'
- original_query: (string) câu hỏi gốc
- requires_inventory_check: (boolean) có cần kiểm tra kho không
- requires_order_placement: (boolean) khách có ý định đặt hàng không

CHÚ Ý:
- Phản hồi của bạn PHẢI là một đối tượng JSON thuần túy, KHÔNG bao gồm bất kỳ định dạng markdown nào như ```json hoặc ```. 
- Chỉ trả về đối tượng JSON với các trường như mô tả, không thêm văn bản trước hoặc sau JSON.

Ví dụ output:
{"product_details": "iPhone 15 Pro Max 256GB màu Titan tự nhiên", "customer_intent": "place_order", "original_query": "Tôi muốn mua iPhone 15 Pro Max", "requires_inventory_check": true, "requires_order_placement": true}
            """,
            planner=self.planner
    )

class InventoryAgent:
    def __init__(self, client, tools=None):
        self.agent = Agent(
            name="inventory_agent",
            model=client,
            description="Kiểm tra tồn kho và giá sản phẩm bằng cách gọi tool check_inventory_detail",
            instruction="""Bạn có tool "check_inventory_detail" để kiểm tra thông tin sản phẩm từ database.
NHIỆM VỤ:
1. Phân tích thông tin sản phẩm từ input (product_details)
2. LUÔN LUÔN gọi tool "check_inventory_detail" với các tham số:
   - product: Tên sản phẩm (bắt buộc, ví dụ: "iPhone 15 Pro Max")
   - storage: Dung lượng nếu có (ví dụ: "256GB", hoặc "" nếu không có)
   - color: Màu sắc nếu có (ví dụ: "Titan tự nhiên", hoặc "" nếu không có)
3. Sau khi nhận kết quả từ tool, trả về JSON với các trường:
   - product_name, color, storage, stock_status, price, quantity, message

QUAN TRỌNG:
- BẮT BUỘC phải gọi tool check_inventory_detail, KHÔNG TỰ TẠO dữ liệu giả
- Trả về JSON thuần túy không có markdown
- Ví dụ: {"product_name": "iPhone 15", "storage": "256GB", "color": "Black", "stock_status": "in_stock", "price": 27990000, "quantity": 10}
            """,
            tools=tools if tools else [],
        )

class OrderAgent:
    def __init__(self, client, tools=None):
        self.agent = Agent(
            name="order_agent",
            model=client,
            description="Tạo đơn hàng bằng cách gọi tool create_customer_order",
            instruction="""Bạn có tool "create_customer_order" để tạo đơn hàng.
NHIỆM VỤ:
1. Kiểm tra xem có đủ thông tin để tạo đơn hàng không
2. Nếu có đủ thông tin (sản phẩm còn hàng, có thông tin khách):
- Tạo order_id duy nhất (dùng uuid)
- Tạo dictionary với các trường: order_id, product, color, storage, quantity, total_price, customer_info (gồm customer_name và conversation_id)
- GỌI tool "create_customer_order" với tham số order_details là dictionary đó
3. Trả về JSON với order_created=true/false và thông tin đơn hàng

QUAN TRỌNG:
- BẮT BUỘC phải gọi tool create_customer_order để lưu đơn hàng
- KHÔNG TỰ TẠO kết quả giả mà không gọi tool
- Trả về JSON thuần túy: {"order_created": true, "order_details": {...}, "message": "..."}
            """,
            tools=tools if tools else [],
        )

class ConsultantAgent:
    def __init__(self, client, tools=None):
        self.planner = BuiltInPlanner(
            thinking_config=types.ThinkingConfig(
                include_thoughts=True,
                thinking_budget=1024,
            )
        )
        self.agent = Agent(
            name="consultant_agent",
            model=client,
            description="Tổng hợp và tư vấn cho khách hàng",
            instruction="""Tổng hợp tất cả thông tin từ các bước trước để đưa ra câu trả lời cuối cùng cho khách hàng.
- Dựa trên kết quả từ analysis_agent ('customer_intent', 'product_details'), inventory_agent ('stock_status', 'price'), và order_agent ('order_created', 'message'):

1. Nếu đơn hàng được tạo thành công ('order_created' là true):
    - Thông báo rằng đơn hàng đã được đặt thành công
    - Bao gồm thông tin sản phẩm, giá, số lượng
    - Cung cấp order_id để khách theo dõi
    - Thêm lời cảm ơn thân thiện
    
2. Nếu không đặt được đơn hàng:
    - Giải thích lý do (hết hàng, thiếu thông tin, khách không muốn đặt)
    - Đưa ra gợi ý hoặc sản phẩm thay thế (nếu có)
    
3. Nếu khách chỉ hỏi thông tin hoặc giá sản phẩm:
    - Cung cấp thông tin chi tiết về sản phẩm
    - Giá cả, tình trạng kho
    - Tư vấn thêm về đặc điểm nổi bật
    
- Đảm bảo câu trả lời thân thiện, dễ hiểu, và phù hợp với ngữ cảnh của khách hàng.

CHÚ Ý:
- Trả về một câu trả lời văn bản hoàn chỉnh (KHÔNG phải JSON)
- Câu trả lời phải tự nhiên như một nhân viên tư vấn thực sự
- Thân thiện, chuyên nghiệp và cung cấp đầy đủ thông tin
            """,
            tools=tools or [],
            planner=self.planner
    )
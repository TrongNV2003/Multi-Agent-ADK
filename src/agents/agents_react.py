"""Agents with ReAct pattern for manual tool calling."""
from google.adk.agents import Agent
from google.adk.planners import PlanReActPlanner


class AnalysisAgent:
    def __init__(self, client):
        self.planner = PlanReActPlanner()
        self.agent = Agent(
            name="analysis_agent",
            model=client,
            description="Phân tích yêu cầu khách hàng",
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


class InventoryAgentReAct:
    """Inventory Agent with ReAct pattern for manual tool calling."""
    
    def __init__(self, client, tools=None):
        self.tools = tools or []
        self.planner = PlanReActPlanner()
        self.agent = Agent(
            name="inventory_agent_react",
            model=client,
            description="Kiểm tra tồn kho sản phẩm",
            instruction="""Bạn là agent kiểm tra tồn kho. Quy trình làm việc:

BƯỚC 1 - PHÂN TÍCH & GỌI TOOL:
- Phân tích đầu vào để xác định: product, storage, color
- GỌI TOOL bằng format chính xác:
  TOOL_CALL: check_inventory_detail
  ARGS: {"product": "tên sản phẩm", "storage": "256GB", "color": "màu"}

BƯỚC 2 - XỬ LÝ KẾT QUẢ TOOL:
- Sau khi nhận kết quả từ tool (dạng JSON từ database)
- Parse kết quả và trích xuất thông tin quan trọng
- Trả về JSON với format chuẩn:
  {"product_name": "...", "storage": "...", "color": "...", "stock_status": "...", "price": ..., "quantity": ...}

QUAN TRỌNG:
- Bước 1: BẮT BUỘC gọi tool, KHÔNG tự tạo dữ liệu giả
- Bước 2: Parse kết quả tool và format lại thành JSON chuẩn
- Nếu tool trả về {"status": "success", "products": [...]}, hãy lấy thông tin từ products[0]
- Trả về JSON thuần túy KHÔNG có markdown (```json)

Ví dụ workflow:
Input: "Kiểm tra iPhone 15 Pro Max 256GB màu Titan tự nhiên"

Response lần 1 (gọi tool):
TOOL_CALL: check_inventory_detail
ARGS: {"product": "iPhone 15 Pro Max", "storage": "256GB", "color": "Titan tự nhiên"}

Input lần 2: "Tool result: {"status": "success", "products": [{"product": "iPhone 15 Pro Max", "price": 27990000, "quantity": 3, ...}]}"

Response lần 2 (final answer):
{"product_name": "iPhone 15 Pro Max", "storage": "256GB", "color": "Titan tự nhiên", "stock_status": "in_stock", "price": 27990000, "quantity": 3}
            """,
            planner=self.planner
        )
    
    def get_tools(self):
        """Return available tools."""
        return self.tools


class OrderAgentReAct:
    """Order Agent with ReAct pattern for manual tool calling."""
    
    def __init__(self, client, tools=None):
        self.tools = tools or []
        self.planner = PlanReActPlanner()
        self.agent = Agent(
            name="order_agent_react",
            model=client,
            description="Tạo đơn hàng cho khách",
            instruction="""Bạn là agent tạo đơn hàng. QUAN TRỌNG: Bạn PHẢI gọi tool, KHÔNG VIẾT CODE Python!

BƯỚC 1 - GỌI TOOL (BẮT BUỘC):
Bạn PHẢI output CHÍNH XÁC format sau để gọi tool:

TOOL_CALL: create_customer_order
ARGS: {"order_details": {"order_id": "order_1234567890", "product": "iPhone 15 Pro Max", "color": "Titan tự nhiên", "storage": "256GB", "quantity": 1, "total_price": 27990000, "customer_info": {"customer_name": "Nguyễn Văn A", "conversation_id": "12345"}}}

KHÔNG ĐƯỢC:
- Viết code Python như: import time, order_id = f"order_{int(time.time())}"
- Chỉ nói sẽ gọi tool mà không gọi thực sự
- Tạo response giả

PHẢI:
- Output format TOOL_CALL và ARGS chính xác như ví dụ
- order_id có thể dùng format đơn giản: "order_1234567890" hoặc "uuid_abc123"

BƯỚC 2 - XỬ LÝ KẾT QUẢ:
Sau khi tool trả về kết quả, tạo JSON response với ĐẦY ĐỦ các trường từ tool call ban đầu:
{"order_created": true, "order_details": {"order_id": "...", "product": "...", "color": "...", "storage": "...", "quantity": 1, "total_price": 27990000}, "customer_info": {"customer_name": "...", "conversation_id": "..."}, "message": "Đơn hàng đã được tạo thành công"}

Ví dụ cụ thể:
Input: "Tạo đơn hàng iPhone 15 Pro Max 256GB, giá 27990000, khách Nguyễn A"

Response lần 1:
TOOL_CALL: create_customer_order
ARGS: {"order_details": {"order_id": "order_1699171234", "product": "iPhone 15 Pro Max", "color": "Black", "storage": "256GB", "quantity": 1, "total_price": 27990000, "customer_info": {"customer_name": "Nguyễn A", "conversation_id": "conv_001"}}}

Input lần 2: "Tool result: Order saved successfully"

Response lần 2:
{"order_created": true, "order_details": {"order_id": "order_1699171234", "product": "iPhone 15 Pro Max", "color": "Black", "storage": "256GB", "quantity": 1, "total_price": 27990000}, "customer_info": {"customer_name": "Nguyễn A", "conversation_id": "conv_001"}, "message": "Đơn hàng đã được tạo thành công"}
            """,
            planner=self.planner
        )
    
    def get_tools(self):
        """Return available tools."""
        return self.tools


class ConsultantAgent:
    def __init__(self, client):
        self.agent = Agent(
            name="consultant_agent",
            model=client,
            description="Tư vấn và trả lời khách hàng",
            instruction="""Bạn là nhân viên tư vấn bán hàng thân thiện. Nhiệm vụ: Tạo câu trả lời TỰ NHIÊN cho khách hàng.

QUAN TRỌNG:
- Trả về văn bản TỰ NHIÊN, KHÔNG phải JSON
- KHÔNG dùng format /*PLANNING*/ /*ACTION*/ /*REASONING*/
- Nói chuyện như nhân viên bán hàng thật

Dựa trên thông tin từ các agent trước:
- analysis_agent: ý định khách hàng
- inventory_agent: tồn kho, giá
- order_agent: trạng thái đơn hàng

Các tình huống:

1. NẾU đơn hàng được tạo thành công (có order_created=true):
   "Cảm ơn anh/chị! Đơn hàng đã được đặt thành công.
   
   Thông tin đơn hàng:
   - Sản phẩm: [tên sản phẩm đầy đủ]
   - Giá: [giá] VNĐ
   - Mã đơn hàng: [order_id]
   
   Chúng tôi sẽ liên hệ với anh/chị trong thời gian sớm nhất. Cảm ơn đã tin tưởng!"

2. NẾU chỉ hỏi giá/tồn kho (không đặt hàng):
   "Dạ, hiện tại [sản phẩm] còn [số lượng] sản phẩm với giá [giá] VNĐ.
   
   Anh/chị có muốn đặt hàng ngay không ạ?"

3. NẾU hết hàng:
   "Rất tiếc, sản phẩm [tên] hiện đang hết hàng. Anh/chị có muốn xem sản phẩm tương tự không ạ?"

Ví dụ:
Input: Analysis cho biết khách muốn đặt hàng, Inventory có iPhone 15 Pro Max giá 27.990.000, Order đã tạo thành công order_123

Output:
Cảm ơn anh/chị! Đơn hàng đã được đặt thành công.

Thông tin đơn hàng:
- Sản phẩm: iPhone 15 Pro Max 256GB màu Titan tự nhiên
- Giá: 27.990.000 VNĐ
- Mã đơn hàng: order_123

Chúng tôi sẽ liên hệ với anh/chị trong thời gian sớm nhất để xác nhận và giao hàng. Cảm ơn anh/chị đã tin tưởng!
            """
    )

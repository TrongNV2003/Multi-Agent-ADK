from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class CustomerIntent(str, Enum):
    """Customer intent types."""
    CHECK_INVENTORY = "check_inventory_price"
    PLACE_ORDER = "place_order"
    GENERAL_QUERY = "general_query"
    PRODUCT_INFO = "product_info"


class StockStatus(str, Enum):
    """Stock status types."""
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    LOW_STOCK = "low_stock"
    NOT_CHECKED = "not_checked"


# ==================== Analysis Agent Schemas ====================
class AnalysisResult(BaseModel):
    """Structured analysis result."""
    product_details: str = Field(
        description="Mô tả chi tiết sản phẩm khách quan tâm (ví dụ: 'iPhone 15 Pro Max 256GB màu Titan tự nhiên')"
    )
    customer_intent: CustomerIntent = Field(
        description="Ý định của khách hàng"
    )
    original_query: str = Field(
        description="Câu hỏi gốc của khách hàng"
    )
    requires_inventory_check: bool = Field(
        default=False,
        description="Có cần kiểm tra kho/giá không"
    )
    requires_order_placement: bool = Field(
        default=False,
        description="Khách có ý định đặt hàng không"
    )

class AnalysisOutput(BaseModel):
    """Output schema for Analysis Agent."""
    analysis: str = Field(
        description="JSON string chứa kết quả phân tích (sẽ được parse thành AnalysisResult)"
    )


# ==================== Inventory Agent Schemas ====================
class InventoryCheckResult(BaseModel):
    """Structured inventory check result."""
    product_name: str = Field(
        description="Tên sản phẩm đã kiểm tra"
    )
    color: Optional[str] = Field(
        None,
        description="Màu sắc của sản phẩm"
    )
    storage: Optional[str] = Field(
        None,
        description="Dung lượng của sản phẩm"
    )
    stock_status: StockStatus = Field(
        description="Trạng thái tồn kho"
    )
    price: Optional[float] = Field(
        None,
        description="Giá sản phẩm (VND)"
    )
    quantity: Optional[int] = Field(
        None,
        description="Số lượng còn lại trong kho"
    )
    message: Optional[str] = Field(
        None,
        description="Thông báo bổ sung"
    )

class CheckInventoryOutput(BaseModel):
    """Output schema for Inventory Agent."""
    check_inventory: str = Field(
        description="JSON string chứa kết quả kiểm tra kho (sẽ được parse thành InventoryCheckResult)"
    )


# ==================== Order Agent Schemas ====================
class CustomerInfo(BaseModel):
    """Customer information."""
    customer_name: str = Field(
        default="Guest",
        description="Tên khách hàng"
    )
    conversation_id: str = Field(
        description="ID của cuộc hội thoại"
    )
    previous_interactions: Optional[str] = Field(
        None,
        description="Các tương tác trước đó"
    )

class OrderDetails(BaseModel):
    """Order details structure."""
    order_id: str = Field(
        description="ID đơn hàng (UUID)"
    )
    product: str = Field(
        description="Tên sản phẩm"
    )
    color: Optional[str] = Field(
        None,
        description="Màu sắc"
    )
    storage: Optional[str] = Field(
        None,
        description="Dung lượng"
    )
    quantity: int = Field(
        default=1,
        description="Số lượng"
    )
    total_price: float = Field(
        description="Tổng giá (VND)"
    )
    customer_info: CustomerInfo = Field(
        description="Thông tin khách hàng"
    )

class OrderCreationResult(BaseModel):
    """Result of order creation."""
    order_created: bool = Field(
        description="Đơn hàng có được tạo thành công không"
    )
    order_details: Optional[OrderDetails] = Field(
        None,
        description="Chi tiết đơn hàng nếu được tạo"
    )
    message: str = Field(
        description="Thông báo về trạng thái tạo đơn hàng"
    )

class CreateOrderOutput(BaseModel):
    """Output schema for Order Agent."""
    create_order: str = Field(
        description="JSON string chứa kết quả tạo đơn hàng (sẽ được parse thành OrderCreationResult)"
    )


# ==================== Tool Input Schemas ====================
class CreateOrderInput(BaseModel):
    """Input schema for Create Order tool."""
    order_details: str = Field(
        ..., 
        description="Order details in JSON format (stringified OrderDetails)"
    )

class CheckInventoryInput(BaseModel):
    """Input schema for Check Inventory tool."""
    product: str = Field(
        ..., 
        description="Name of the product (e.g., 'iPhone 15 Pro Max')"
    )
    storage: Optional[str] = Field(
        None, 
        description="Storage capacity (e.g., '256GB')"
    )
    color: Optional[str] = Field(
        None, 
        description="Color of the product (e.g., 'Titan tự nhiên')"
    )


# ==================== API Schemas ====================
class ChatRequest(BaseModel):
    """Chat request schema for API."""
    query: str = Field(
        ...,
        description="Customer query",
        min_length=1,
        max_length=2000
    )
    initial_context_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Initial context data for the conversation"
    )
    user_id: Optional[str] = Field(
        "default_user",
        description="User identifier"
    )
    session_id: Optional[str] = Field(
        None,
        description="Session identifier (auto-generated if not provided)"
    )

class ChatResponse(BaseModel):
    """Chat response schema for API."""
    customer_response: str = Field(
        description="Response message for the customer"
    )
    status: str = Field(
        description="Status of the request (success/error)"
    )
    session_id: Optional[str] = Field(
        None,
        description="Session identifier"
    )
    token_usage: Optional[Dict[str, Any]] = Field(
        None,
        description="Token usage information"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if status is error"
    )
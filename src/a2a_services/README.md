# A2A Remote Microservices

Các microservice Agent-to-Agent theo chuẩn A2A protocol của Google ADK.

## Tổng quan

Mỗi agent chuyên môn được triển khai như một **microservice độc lập** có thể:
- Chạy trên port riêng
- Scale độc lập theo tải
- Cung cấp Agent Card chuẩn theo A2A protocol
- Giao tiếp với nhau qua HTTP/JSON-RPC

## Cấu trúc

```
src/a2a_services/
├── __init__.py
├── base.py                  # LLM client factory dùng chung
├── analysis_agent.py        # Analysis Agent (port 9101)
├── inventory_agent.py       # Inventory Agent (port 9102)  
├── order_agent.py           # Order Agent (port 9103)
└── consultant_agent.py      # Consultant Agent (port 9104)
```

## Agent Cards

Mỗi agent định nghĩa **AgentCard** chuẩn từ `a2a.types.AgentCard` với các trường:
- `name`: Agent identifier
- `url`: Base URL của service
- `description`: Mô tả chức năng
- `version`: Phiên bản (semantic versioning)
- `capabilities`: Dict chứa danh sách intent/khả năng
- `skills`: Danh sách skill (thường để rỗng)
- `defaultInputModes`: Loại input chấp nhận (text/plain, application/json...)
- `defaultOutputModes`: Loại output trả về
- `supportsAuthenticatedExtendedCard`: Bool cho extended card authentication

## Chạy từng Service
### 1. Analysis Agent
```bash
conda activate trongnv
python -m src.a2a_services.analysis_agent
```

Hoặc với uvicorn:
```bash
uvicorn src.a2a_services.analysis_agent:app --host 0.0.0.0 --port 9101
```

### 2. Inventory Agent
```bash
conda activate trongnv
python -m src.a2a_services.inventory_agent
```

### 3. Order Agent
```bash
conda activate trongnv
python -m src.a2a_services.order_agent
```

### 4. Consultant Agent
```bash
conda activate trongnv
python -m src.a2a_services.consultant_agent
```

## Kiểm tra Agent Card

Sau khi chạy một service, kiểm tra Agent Card endpoint:

```bash
# Ví dụ với Analysis Agent
curl http://localhost:9101/.well-known/agent-card.json

# Kết quả trả về JSON chứa thông tin agent card
```

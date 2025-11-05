# Multi-Agent System with MCP SSE Server

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A sophisticated multi-agent system for e-commerce consultation and order processing, powered by **Google ADK** and **Model Context Protocol (MCP)** with Server-Sent Events (SSE) architecture.

## 🎯 Overview

This system implements an intelligent sales assistant using a ReAct (Reasoning + Acting) pattern with multiple specialized agents that collaborate to:
- Analyze customer inquiries and product requirements
- Check real-time inventory availability and pricing
- Process and persist customer orders
- Provide natural language consultation

The agents communicate with an MCP SSE server that interfaces with MongoDB for product inventory and order management.

## 🏗️ Architecture

### Agent Pipeline (ReAct Pattern)
```
User Query → Analysis Agent → Inventory Agent → Order Agent → Consultant Agent → Response
                    ↓              ↓               ↓
                    └──────── Tool Executor ────────┘
                                    ↓
                            MCP SSE Server
                                    ↓
                                MongoDB
```

### Core Agents

1. **Analysis Agent**: Parses customer intent and extracts product details
2. **Inventory Agent (ReAct)**: Calls `check_inventory_detail` tool to query product availability
3. **Order Agent (ReAct)**: Calls `create_customer_order` tool to persist orders
4. **Consultant Agent**: Generates natural language responses for customers

### Technology Stack

- **Agent Framework**: Google ADK (Agent Development Kit)
- **LLM Integration**: LiteLLM with vLLM backend
- **Protocol**: Model Context Protocol (MCP) with SSE transport
- **Database**: MongoDB for inventory and order storage
- **UI**: Streamlit for interactive chat interface
- **Containerization**: Docker & Docker Compose

## 🚀 Features

- ✅ **ReAct Pattern Implementation**: Manual tool-calling with iterative reasoning and action execution
- ✅ **MCP SSE Integration**: Async communication with MCP server via Server-Sent Events
- ✅ **Real-time Inventory Lookup**: Query product availability, pricing, and stock quantities
- ✅ **Order Management**: Create, persist, and track customer orders
- ✅ **Robust Parsing**: Handle nested JSON in agent outputs with brace-counting extraction
- ✅ **Session Management**: Maintain conversation context across multiple turns
- ✅ **Streamlit UI**: User-friendly chat interface with agent status indicators

## 📋 Prerequisites

- Python 3.11+
- Docker & Docker Compose (for containerized deployment)
- vLLM server running at `http://localhost:8000/v1` (or configure your own endpoint)

## 🛠️ Installation

### Local Development

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd agentADK
```

2. **Create and activate conda environment**
```bash
conda create -n trongnv python=3.11
conda activate trongnv
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Start MongoDB**
```bash
sudo systemctl start mongod
```

5. **Configure environment** (optional)
```bash
cp .env.example .env
# Edit .env with your settings
```

### Docker Deployment

1. **Build and run all services**
```bash
docker-compose up --build
```

This will start:
- MongoDB on `localhost:27017`
- MCP SSE Server on `localhost:8000`
- Streamlit UI on `localhost:8501`

## 🚀 Usage

### Start MCP SSE Server

```bash
conda activate trongnv
python mcp_server.py
```

The MCP server exposes:
- SSE endpoint: `http://localhost:8000/sse`
- Tools:
  - `get_product_info`: Query inventory by product name, storage, color
  - `create_order`: Persist customer orders
  - `get_order`: Retrieve order details

### Run Multi-Agent Pipeline (CLI)

```bash
conda activate trongnv
python main.py
```

Example interaction:
```
User: "Tôi muốn mua iPhone 15 Pro Max 256GB màu Titan tự nhiên còn hàng không? Giá bao nhiêu?"

Agent Response:
"Chào bạn! iPhone 15 Pro Max 256GB màu Titan tự nhiên hiện đang có sẵn với giá 27,990,000 VNĐ. 
Chúng tôi còn 3 máy trong kho. Bạn có muốn đặt hàng ngay không?"
```

### Run Streamlit UI

```bash
conda activate trongnv
python -m streamlit run src/ui/app.py
```

Navigate to `http://localhost:8501` in your browser.

**UI Features:**
- Real-time chat with agent
- Order details display panel
- Input disabled while agent is processing (prevents concurrent queries)
- Session persistence across page refreshes

## 📁 Project Structure

```
agentADK/
├── src/
│   ├── agents/
│   │   ├── agents.py              # Original agent definitions
│   │   └── agents_react.py        # ReAct-style agents with tool instructions
│   ├── tools/
│   │   ├── get_products.py        # MCP inventory lookup wrapper
│   │   └── create_order.py        # MCP order creation wrapper
│   ├── utils/
│   │   ├── react_executor.py     # Tool call parser and executor
│   │   └── metrics.py             # Performance metrics
│   ├── config/
│   │   ├── settings.py            # Environment configuration
│   │   └── schemas.py             # Pydantic data models
│   ├── db/
│   │   ├── connector.py           # MongoDB connection
│   │   └── insert_data.py         # Sample data insertion
│   ├── ui/
│   │   └── app.py                 # Streamlit interface
│   ├── pipeline.py                # Original multi-agent pipeline
│   └── pipeline_react.py          # ReAct pipeline with manual tool execution
│
├── mcp_server.py                  # MCP SSE server entry point
├── main.py                        # CLI entry point
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Acknowledgments

- **Google ADK**: Agent framework and orchestration
- **Model Context Protocol**: Standardized tool-calling protocol
- **LiteLLM**: Unified LLM API interface
- **vLLM**: High-performance inference server
- **Streamlit**: Rapid UI prototyping

import re
import json
import asyncio
import streamlit as st
from loguru import logger

from src.pipeline_react import MultiAgentsReAct


st.set_page_config(
    page_title="Multi-Agent System",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
    <style>
        .chat-container {
            max-width: 1000px;
            margin: 0 auto;
        }
        .user-message, .bot-message {
            border-radius: 1.5rem;
            padding: .625rem 1.25rem;
            margin: 5px 0;
            display: inline-block;
            max-width: 80%;
        }
        .user-message {
            background-color: rgba(50, 50, 50, .85);
            text-align: right;
            color: white;
            font-size: 18px;
            align-self: flex-end;
        }
        .bot-message {
            background-color: transparent;
            color: white;
            font-size: 18px;
            align-self: flex-start;
        }
        .thinking-step {
            background-color: rgba(80, 80, 80, 0.5);
            padding: 10px;
            border-radius: 1.5rem;
            margin: 5px 0;
            opacity: 0.7;
            max-width: 70%;
        }
        .order-details {
            background-color: rgba(0, 100, 0, 0.5);
            padding: 20px;
            border-radius: 1.5rem;
            max-width: 70%;
            color: white;
            font-size: 18px;
        }
        .error-step {
            background-color: rgba(255, 0, 0, 0.5);
            padding: 10px;
            border-radius: 1.5rem;
            margin: 5px 0;
            max-width: 70%;
        }
        .chat {
            display: flex;
            flex-direction: column;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown("# :rainbow[Agentias - Multi-Agent System]")
st.sidebar.header("Cài đặt")

if "pipeline" not in st.session_state:
    st.session_state.pipeline = MultiAgentsReAct()
    logger.info("MultiAgentsReAct pipeline initialized")

st.sidebar.subheader("Thông tin khách hàng")
customer_name = st.sidebar.text_input("Tên khách hàng", value="Nguyễn Văn Trọng")
previous_interactions = st.sidebar.text_area("Lịch sử tương tác", value="Đã từng hỏi về iPad Air.")

show_details = st.sidebar.checkbox("Hiển thị chi tiết các bước", value=False)

def strip_ansi(text):
    """Loại bỏ mã ANSI escape từ chuỗi."""
    ansi_regex = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_regex.sub('', text)

async def query_processing_async(query_text, context_data, pipeline):
    """Process query using ReAct pipeline."""
    try:
        result = await pipeline.run(
            query=query_text,
            initial_context_data=context_data,
            user_id=context_data.get("customer_name", "default_user"),
            session_id=None
        )
        return result
    except Exception as e:
        logger.error(f"Error in query processing: {e}", exc_info=True)
        return {
            "customer_response": f"Xin lỗi, đã xảy ra lỗi: {str(e)}",
            "status": "error",
            "error": str(e)
        }

def display_task_outputs(result, show_details):
    """Display task outputs if show_details is enabled."""
    if not show_details:
        return
    
    with st.expander("Chi tiết các bước xử lý", expanded=False):
        task_outputs = []
        for i in range(1, 5):
            task_key = f"task{i}_output"
            if task_key in result and result[task_key]:
                task_outputs.append(result[task_key])
        
        for i, task in enumerate(task_outputs, 1):
            agent_name = task.get("agent", f"Agent {i}")
            output = task.get("output", "")
            
            st.markdown(f"**{i}. {agent_name}**")
            
            try:
                if isinstance(output, str):
                    output_json = json.loads(output)
                    st.json(output_json)
                else:
                    st.json(output)
            except:
                st.code(output[:500] + ("..." if len(output) > 500 else ""), language="text")
            
            st.markdown("---")

def display_order_details(order_details):
    """Display order details in a nice box."""
    if order_details:
        order_html = (
            f'<div class="order-details">'
            f'<strong>✅ Đơn hàng đã được tạo thành công!</strong><br><br>'
            f'<strong>Mã đơn hàng:</strong> {order_details.get("order_id", "N/A")}<br>'
            f'<strong>Sản phẩm:</strong> {order_details.get("product", "Unknown")}<br>'
            f'<strong>Màu sắc:</strong> {order_details.get("color", "Unknown")}<br>'
            f'<strong>Bộ nhớ:</strong> {order_details.get("storage", "Unknown")}<br>'
            f'<strong>Số lượng:</strong> {order_details.get("quantity", 1)}<br>'
            f'<strong>Tổng giá:</strong> {order_details.get("total_price", 0):,.0f} VNĐ<br>'
            f'<strong>Khách hàng:</strong> {order_details.get("customer_info", {}).get("customer_name", "Guest")}<br>'
            f'</div>'
        )
        st.markdown(f'<div class="chat-container"><div class="chat">{order_html}</div></div>', unsafe_allow_html=True)

def main():
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
        initial_bot_message = "Xin chào! Tôi là Agentias. Hôm nay tôi có thể giúp gì cho bạn?"
        st.session_state.chat_history.append({"role": "assistant", "content": initial_bot_message})

    if "session_id" not in st.session_state:
        import uuid
        st.session_state.session_id = str(uuid.uuid4())
        logger.info(f"New session created: {st.session_state.session_id}")

    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    for message in st.session_state.chat_history:
        if message["role"] == "user":
            st.markdown(f'<div class="chat"><div class="user-message">{message["content"]}</div></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat"><div class="bot-message">{message["content"]}</div></div>', unsafe_allow_html=True)
            
            if "order_details" in message:
                display_order_details(message["order_details"])
    st.markdown('</div>', unsafe_allow_html=True)

    query_text = st.chat_input("Hỏi Agentias điều gì đó...")
    if query_text:
        initial_context = {
            "conversation_id": st.session_state.session_id,
            "customer_name": customer_name,
            "previous_interactions": previous_interactions
        }
        
        st.session_state.chat_history.append({"role": "user", "content": query_text})
        st.markdown(f'<div class="chat-container"><div class="chat"><div class="user-message">{query_text}</div></div></div>', unsafe_allow_html=True)
        
        with st.spinner("Đang xử lý yêu cầu của bạn..."):
            result = asyncio.run(query_processing_async(
                query_text, 
                initial_context,
                st.session_state.pipeline
            ))
        
        final_answer = result.get("customer_response", "Xin lỗi, tôi không thể xử lý yêu cầu của bạn lúc này.")
        order_details = None
        
        task3_output = result.get("task3_output")
        if task3_output:
            try:
                task3_data = task3_output.get("output", "") if isinstance(task3_output, dict) else task3_output
                if isinstance(task3_data, str):
                    task3_json = json.loads(task3_data)
                else:
                    task3_json = task3_data
                    
                if isinstance(task3_json, dict) and task3_json.get("order_created") and "order_details" in task3_json:
                    order_details = task3_json["order_details"]
            except Exception as e:
                logger.debug(f"Could not extract order details: {e}")
        
        assistant_message = {"role": "assistant", "content": final_answer}
        if order_details:
            assistant_message["order_details"] = order_details
        st.session_state.chat_history.append(assistant_message)
        
        st.markdown(
            f'<div class="chat-container"><div class="chat"><div class="bot-message">{final_answer}</div></div></div>',
            unsafe_allow_html=True
        )
        
        if order_details:
            display_order_details(order_details)
        
        display_task_outputs(result, show_details)
        
        if result.get("status") == "success":
            st.sidebar.success(f"✅ Request processed successfully")
            st.sidebar.info(f"Session: {result.get('session_id', 'N/A')[:8]}...")
        else:
            st.sidebar.error(f"Error: {result.get('error', 'Unknown error')}")
        
        st.rerun()

def health_check():
    st.sidebar.markdown("---")
    st.sidebar.header("Thông tin hệ thống")
    
    if "session_id" in st.session_state:
        st.sidebar.text(f"Session: {st.session_state.session_id[:13]}...")
    
    if "chat_history" in st.session_state:
        msg_count = len([m for m in st.session_state.chat_history if m["role"] == "user"])
        st.sidebar.text(f"💬 Messages: {msg_count}")
    
    if st.sidebar.button("🔍 Kiểm tra trạng thái"):
        st.sidebar.success("✅ Hệ thống hoạt động bình thường!")
    
    # Reset conversation button
    if st.sidebar.button("🔄 Làm mới cuộc hội thoại"):
        st.session_state.chat_history = []
        import uuid
        st.session_state.session_id = str(uuid.uuid4())
        st.sidebar.info("Đã tạo session mới!")
        st.rerun()

if __name__ == "__main__":
    main()
    health_check()
    
# python -m streamlit run multi_agents/ui/main.py
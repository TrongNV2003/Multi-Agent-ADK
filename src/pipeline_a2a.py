import json
from typing import Dict, Any, Optional
from loguru import logger

from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from src.agents.routes import (
    AgentRegistry,
    AnalysisAgent,
    InventoryAgent,
    OrderAgent,
    ConsultantAgent,
)
from src.handlers.invoke_agents import (
    handle_inventory_agent_call,
    handle_order_agent_call
)


class A2APipeline:
    """
    Pipeline using Agent-to-Agent communication (Agent Card pattern).
    Flow: User → Analysis → [Inventory, Order] → Consultant → Response.
    """
    def __init__(self):
        self.app_name = "a2a_pipeline"
        
        self.session_service = InMemorySessionService()
        
        self.registry = AgentRegistry()
        
        self.analysis_agent = AnalysisAgent()
        self.inventory_agent = InventoryAgent()
        self.order_agent = OrderAgent()
        self.consultant_agent = ConsultantAgent()
        
        self.analysis_runner = Runner(
            agent=self.analysis_agent.agent,
            app_name=f"{self.app_name}:analysis",
            session_service=self.session_service
        )
        
        self.inventory_runner = Runner(
            agent=self.inventory_agent.agent,
            app_name=f"{self.app_name}:inventory",
            session_service=self.session_service
        )
        
        self.order_runner = Runner(
            agent=self.order_agent.agent,
            app_name=f"{self.app_name}:order",
            session_service=self.session_service
        )
        
        self.consultant_runner = Runner(
            agent=self.consultant_agent.agent,
            app_name=f"{self.app_name}:consultant",
            session_service=self.session_service
        )
        
        # Each agent is independent and registered via registry
        logger.info("[Pipeline] Registering agents with their handlers")
        self.registry.register(
            name="inventory_agent",
            agent=self.inventory_agent.agent,
            handler=lambda query, context: handle_inventory_agent_call(
                query, context, self.inventory_runner, self.inventory_agent
            )
        )
        
        self.registry.register(
            name="order_agent",
            agent=self.order_agent.agent,
            handler=lambda query, inventory_info, customer_info: handle_order_agent_call(
                query, inventory_info, customer_info, self.order_runner, self.order_agent
            )
        )
    
    async def _create_agent_session(self, runner: Runner, base_session):
        """Create or reuse a derived session for a specific agent runner."""
        agent_name = getattr(runner.agent, "name", "agent")
        return await runner.session_service.create_session(
            app_name=runner.app_name,
            user_id=base_session.user_id,
            session_id=f"{base_session.id}:{agent_name}"
        )
    
    def list_registered_agents(self) -> list[str]:
        """
        Get list of all registered agent names
        Useful for debugging and monitoring
        """
        return self.registry.list_agents()
    
    async def run(
        self,
        query: str,
        session_id: Optional[str] = None,
        customer_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run A2A pipeline with Agent Card pattern
        
        Flow:
        1. Analysis Agent → analyzes query
        2. Coordinator Agent → calls other agents via their cards
           - Looks up agent cards in registry
           - Calls agents through their handlers
        3. Consultant Agent → generates final response
        
        Args:
            query: User query
            session_id: Optional session ID
            customer_context: Optional customer info
        
        Returns:
            Dict with response and metadata
        """
        logger.info(f"\n\n[A2A Pipeline] Query: {query}")
        
        import uuid

        # Create or fetch root session
        if session_id is None:
            session_id = str(uuid.uuid4())
        session = await self.session_service.create_session(
            app_name=self.app_name,
            user_id="user_001",
            session_id=session_id
        )
        
        logger.info(f"Session: {session_id}")
        
        agent_outputs = []
        
        # Analysis Agent
        analysis_session = await self._create_agent_session(self.analysis_runner, session)
        message = types.Content(role="user", parts=[types.Part(text=query)])
        analysis_result = ""
        async for event in self.analysis_runner.run_async(
            user_id=analysis_session.user_id,
            session_id=analysis_session.id,
            new_message=message
        ):
            if getattr(event, "is_final_response", False):
                if event.content and event.content.parts:
                    analysis_result = event.content.parts[0].text
                break
        
        agent_outputs.append({"agent": "analysis", "output": analysis_result})
        logger.debug(f"Analysis Agent response: {analysis_result}")
        
        try:
            analysis_data = json.loads(analysis_result)
        except:
            logger.warning("Analysis output not JSON, using defaults")
            analysis_data = {
                "requires_inventory_check": False,
                "requires_order_placement": False
            }
        
        # Call Inventory Agent via Registry (if required)
        inventory_result = ""
        inventory_data: Dict[str, Any] = {}
        if analysis_data.get("requires_inventory_check"):
            handler = self.registry.get_handler("inventory_agent")
            if handler:
                try:
                    inventory_result = await handler(
                        query=analysis_data.get("product_details") or query,
                        context=json.dumps(analysis_data, ensure_ascii=False)
                    )
                    agent_outputs.append({
                        "agent": "inventory",
                        "output": inventory_result
                    })
                    try:
                        inventory_data = json.loads(inventory_result) if inventory_result else {}
                    except json.JSONDecodeError:
                        logger.warning("Inventory agent output not JSON parseable")
                except Exception as inv_err:
                    logger.error(f"[A2A Pipeline] Inventory agent failed: {inv_err}", exc_info=True)
            else:
                logger.error("[A2A Pipeline] Inventory agent handler not found in registry")
        
        
        # Call Order Agent via Registry (if required)
        order_result = ""
        order_data: Dict[str, Any] = {}
        if analysis_data.get("requires_order_placement"):
            handler = self.registry.get_handler("order_agent")
            if handler:
                try:
                    order_result = await handler(
                        query=analysis_data.get("product_details") or query,
                        inventory_info=inventory_result or json.dumps({}, ensure_ascii=False),
                        customer_info=json.dumps(customer_context or {
                            "customer_name": "Khách hàng",
                            "conversation_id": session_id
                        }, ensure_ascii=False)
                    )
                    agent_outputs.append({
                        "agent": "order",
                        "output": order_result
                    })
                    try:
                        order_data = json.loads(order_result) if order_result else {}
                    except json.JSONDecodeError:
                        logger.warning("Order agent output not JSON parseable")
                except Exception as order_err:
                    logger.error(f"[A2A Pipeline] Order agent failed: {order_err}", exc_info=True)
            else:
                logger.error("[A2A Pipeline] Order agent handler not found in registry")
        
        # Call Consultant Agent (response)
        customer_info = customer_context or {
            "customer_name": "Khách hàng",
            "conversation_id": session_id
        }
        
        consultant_prompt = f"""
Bạn là Agentias, một Consultant Agent chuyên phản hồi khách hàng dựa trên thông tin từ các agent khác.
Đây là thông tin cá nhân của bạn:
Bạn tên là Agentias, làm việc tại cửa hàng điện thoại di động ABC.
Số điện thoại liên hệ của cửa hàng: 19006789.

Tạo câu trả lời cuối cho khách hàng dựa trên:

Customer Query: {query}

Analysis:
{analysis_result}

Inventory Result:
{inventory_result if inventory_result else "Không kiểm tra"}

Order Result:
{order_result if order_result else "Không tạo đơn"}

Thông tin cá nhân của khách hàng:
{json.dumps(customer_info, ensure_ascii=False, indent=2)}

YÊU CẦU:
- Trả lời thân thiện bằng tiếng Việt
- KHÔNG đưa số điện thoại của khách hàng trong câu trả lời (đây là thông tin cá nhân của họ)
- Không sử dụng /*PLANNING*/, không đưa mã nguồn hoặc pseudo-code
- Chỉ trả lời bằng đoạn văn hoàn chỉnh
"""
        
        consultant_session = await self._create_agent_session(self.consultant_runner, session)
        message = types.Content(role="user", parts=[types.Part(text=consultant_prompt)])
        final_response = ""
        async for event in self.consultant_runner.run_async(
            user_id=consultant_session.user_id,
            session_id=consultant_session.id,
            new_message=message
        ):
            if getattr(event, "is_final_response", False):
                if event.content and event.content.parts:
                    final_response = event.content.parts[0].text
                break
        
        agent_outputs.append({"agent": "consultant", "output": final_response})
        
        if isinstance(final_response, str):
            final_response = final_response.strip()
            if final_response.startswith("{") and final_response.endswith("}"):
                try:
                    parsed = json.loads(final_response)
                    final_response = parsed.get("response", final_response)
                except json.JSONDecodeError:
                    pass
        
        result = {
            "customer_response": final_response or "Xin lỗi, tôi không thể xử lý yêu cầu lúc này.",
            "agent_outputs": agent_outputs,
            "session_id": session_id,
            "status": "success"
        }
        
        logger.info(f"[A2A Pipeline] Consultant Agent response: {final_response}")
        logger.info(f"[A2A Pipeline] Completed for session: {session_id}")
        return result

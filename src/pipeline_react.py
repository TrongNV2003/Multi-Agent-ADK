import json
from loguru import logger
from google.genai import types
from google.adk.runners import Runner
from typing import Dict, Any, Optional
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService

from src.agents.agents_react import (
    AnalysisAgent, 
    InventoryAgentReAct, 
    OrderAgentReAct, 
    ConsultantAgent
)
from src.tools.create_order import create_customer_order
from src.tools.get_products import check_inventory_detail
from src.handlers.react_executor import create_tool_executor_for_pipeline
from src.config.settings import api_config


class MultiAgentsReAct:
    """Multi-agent pipeline with ReAct pattern for manual tool calling."""
    def __init__(self, app_name: str = "sales_pipeline_app"):
        self.app_name = app_name
        
        try:
            self.client = LiteLlm(
                model="openai/Qwen/Qwen3-8B",
                api_base=api_config.base_url_llm,
                api_key=api_config.api_key,
            )
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            raise
        
        self.session_service = InMemorySessionService()

        self.analysis = AnalysisAgent(client=self.client)
        self.inventory = InventoryAgentReAct(
            client=self.client,
            tools=[check_inventory_detail]
        )
        self.order = OrderAgentReAct(
            client=self.client,
            tools=[create_customer_order]
        )
        self.consultant = ConsultantAgent(client=self.client)

        self.analysis_runner = Runner(
            agent=self.analysis.agent,
            app_name=self.app_name,
            session_service=self.session_service,
        )
        self.inventory_runner = Runner(
            agent=self.inventory.agent,
            app_name=self.app_name,
            session_service=self.session_service,
        )
        self.order_runner = Runner(
            agent=self.order.agent,
            app_name=self.app_name,
            session_service=self.session_service,
        )
        self.consultant_runner = Runner(
            agent=self.consultant.agent,
            app_name=self.app_name,
            session_service=self.session_service,
        )

        self.tool_executor = create_tool_executor_for_pipeline(
            check_inventory_func=check_inventory_detail,
            create_order_func=create_customer_order
        )

    async def _run_agent_with_tool_support(
        self,
        runner: Runner,
        prompt: str,
        session_user_id: str,
        session_id_base: str,
        max_iterations: int = 3
    ) -> str:
        """
        Run agent with tool calling support using ReAct pattern.
        
        Args:
            runner: Agent runner
            prompt: Input prompt
            session_user_id: User ID for session
            session_id_base: Base session ID
            max_iterations: Maximum tool calling iterations
            
        Returns:
            Final agent response
        """
        agent_name = getattr(runner.agent, "name", "agent")
        agent_session = await self.session_service.create_session(
            app_name=self.app_name,
            user_id=session_user_id,
            session_id=f"{session_id_base}:{agent_name}",
        )

        current_prompt = prompt
        
        for iteration in range(max_iterations):
            logger.info(f"Agent {agent_name} - Iteration {iteration + 1}/{max_iterations}")
            
            message = types.Content(role="user", parts=[types.Part(text=current_prompt)])
            response_text = ""
            
            async for event in runner.run_async(
                user_id=agent_session.user_id,
                session_id=agent_session.id,
                new_message=message,
            ):
                if getattr(event, "is_final_response", False):
                    if event.content and event.content.parts:
                        response_text = event.content.parts[0].text
                    break
            
            logger.debug(f"Agent {agent_name} output: {response_text}")
            
            tool_result = self.tool_executor.process_agent_output(response_text)
            
            if tool_result["tool_called"]:
                tool_name = tool_result["tool_name"]
                tool_output = tool_result["tool_result"]
                
                logger.info(f"Tool called: {tool_name}")
                
                current_prompt = (
                    f"Bạn đã gọi tool '{tool_name}' và nhận được kết quả:\n"
                    f"{tool_output}\n\n"
                    f"Hãy sử dụng kết quả này để hoàn thành nhiệm vụ và trả về JSON như yêu cầu."
                )
            else:
                logger.info(f"No tool call detected, returning final response")
                return response_text
        
        logger.warning(f"Agent {agent_name} reached max iterations ({max_iterations})")
        return response_text
    
    async def run(
        self,
        query: str,
        initial_context_data: Optional[Dict[str, Any]] = None,
        user_id: str = "default_user",
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run the multi-agent pipeline with ReAct pattern."""
        try:
            if session_id is None:
                import uuid
                session_id = str(uuid.uuid4())

            session = await self.session_service.create_session(
                app_name=self.app_name,
                user_id=user_id,
                session_id=session_id,
            )
            logger.debug(f"Session created: {session.id}")

            async def _run_agent_simple(runner: Runner, prompt: str) -> str:
                """Run agent without tool support (for analysis and consultant)."""
                agent_name = getattr(runner.agent, "name", "agent")
                agent_session = await self.session_service.create_session(
                    app_name=self.app_name,
                    user_id=session.user_id,
                    session_id=f"{session.id}:{agent_name}",
                )

                message = types.Content(role="user", parts=[types.Part(text=prompt)])
                response_text = ""
                async for event in runner.run_async(
                    user_id=agent_session.user_id,
                    session_id=agent_session.id,
                    new_message=message,
                ):
                    if getattr(event, "is_final_response", False):
                        if event.content and event.content.parts:
                            response_text = event.content.parts[0].text
                        break
                return response_text

            agent_outputs = []

            # Step 1: Analysis Agent
            analysis_prompt = query if not initial_context_data else (
                f"Context: {json.dumps(initial_context_data, ensure_ascii=False)}\n"
                f"Câu hỏi khách hàng: {query}"
            )
            analysis_result = await _run_agent_simple(self.analysis_runner, analysis_prompt)
            agent_outputs.append({"agent": "analysis_agent", "output": analysis_result})
            logger.debug(f"Analysis output: {analysis_result}")

            try:
                analysis_data = json.loads(analysis_result) if analysis_result else {}
            except json.JSONDecodeError:
                analysis_data = {}
                logger.warning("Analysis output could not be parsed as JSON.")

            # Step 2: Inventory Agent (with ReAct tool calling)
            inventory_result = ""
            if analysis_data.get("requires_inventory_check"):
                inventory_prompt = (
                    "Dựa trên kết quả phân tích sau, hãy kiểm tra tồn kho:\n"
                    f"{analysis_result}\n\n"
                    "Hãy gọi tool check_inventory_detail với format:\n"
                    "TOOL_CALL: check_inventory_detail\n"
                    'ARGS: {"product": "...", "storage": "...", "color": "..."}'
                )
                inventory_result = await self._run_agent_with_tool_support(
                    self.inventory_runner,
                    inventory_prompt,
                    session.user_id,
                    session.id,
                    max_iterations=3
                )
                agent_outputs.append({"agent": "inventory_agent", "output": inventory_result})
                logger.debug(f"Inventory output: {inventory_result}")

            # Step 3: Order Agent (with ReAct tool calling)
            order_result = ""
            if analysis_data.get("requires_order_placement"):
                customer_context = (
                    f"Customer context: {json.dumps(initial_context_data, ensure_ascii=False)}\n"
                    if initial_context_data
                    else ""
                )

                order_prompt = (
                    "Khởi tạo đơn hàng dựa trên thông tin sau:\n"
                    f"Analysis: {analysis_result}\n"
                    f"Inventory: {inventory_result or 'Không có'}\n"
                    f"{customer_context}\n"
                    "Hãy gọi tool create_customer_order với format:\n"
                    "TOOL_CALL: create_customer_order\n"
                    'ARGS: {"order_details": {...}}'
                )
                order_result = await self._run_agent_with_tool_support(
                    self.order_runner,
                    order_prompt,
                    session.user_id,
                    session.id,
                    max_iterations=3
                )
                agent_outputs.append({"agent": "order_agent", "output": order_result})
                logger.debug(f"Order output: {order_result}")

            # Step 4: Consultant Agent
            customer_context_consultant = (
                f"Customer context: {json.dumps(initial_context_data, ensure_ascii=False)}\n"
                if initial_context_data
                else ""
            )

            consultant_prompt = (
                "Sinh câu trả lời cuối cùng cho khách hàng dựa trên thông tin:\n"
                f"Customer query: {query}\n"
                f"Analysis: {analysis_result}\n"
                f"Inventory: {inventory_result or 'Không kiểm tra'}\n"
                f"Order: {order_result or 'Chưa tạo đơn'}\n"
                f"{customer_context_consultant}"
                "Trả lời thân thiện bằng tiếng Việt."
            )
            final_response = await _run_agent_simple(self.consultant_runner, consultant_prompt)
            agent_outputs.append({"agent": "consultant_agent", "output": final_response})

            result = {
                "customer_response": final_response or "Xin lỗi, tôi không thể xử lý yêu cầu của bạn lúc này.",
                "task1_output": agent_outputs[0] if len(agent_outputs) > 0 else None,
                "task2_output": agent_outputs[1] if len(agent_outputs) > 1 else None,
                "task3_output": agent_outputs[2] if len(agent_outputs) > 2 else None,
                "task4_output": agent_outputs[3] if len(agent_outputs) > 3 else None,
                "session_id": session_id,
                "status": "success",
            }

            logger.info(f"ReAct Pipeline completed successfully for session: {session_id}")
            return result

        except Exception as e:
            logger.error(f"Error in ReAct pipeline run: {e}", exc_info=True)
            return {
                "customer_response": f"Xin lỗi, đã xảy ra lỗi khi xử lý yêu cầu của bạn: {str(e)}",
                "status": "error",
                "error": str(e),
            }

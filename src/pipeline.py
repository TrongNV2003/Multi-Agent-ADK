import json
import asyncio
from loguru import logger
from google.genai import types
from google.adk.runners import Runner
from typing import Dict, Any, Optional
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService

from src.agents.agents import AnalysisAgent, InventoryAgent, OrderAgent, ConsultantAgent
from src.tools.create_order import create_customer_order
from src.tools.get_products import check_inventory_detail
from src.config.settings import api_config


class MultiAgents:
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
        self.inventory = InventoryAgent(client=self.client, tools=[check_inventory_detail])
        self.order = OrderAgent(client=self.client, tools=[create_customer_order])
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

    async def run(
        self,
        query: str,
        initial_context_data: Optional[Dict[str, Any]] = None,
        user_id: str = "default_user",
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run the multi-agent pipeline in four sequential steps."""
        try:
            logger.info(f"Starting pipeline run for query: {query[:100]}...")

            if session_id is None:
                import uuid
                session_id = str(uuid.uuid4())

            session = await self.session_service.create_session(
                app_name=self.app_name,
                user_id=user_id,
                session_id=session_id,
            )
            logger.debug(f"Session created: {session.id}")

            async def _run_agent(runner: Runner, prompt: str) -> str:
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

            analysis_prompt = query if not initial_context_data else (
                f"Context: {json.dumps(initial_context_data, ensure_ascii=False)}\n"
                f"Câu hỏi khách hàng: {query}"
            )
            analysis_result = await _run_agent(self.analysis_runner, analysis_prompt)
            agent_outputs.append({"agent": "analysis_agent", "output": analysis_result})
            logger.debug(f"Analysis output: {analysis_result}")

            try:
                analysis_data = json.loads(analysis_result) if analysis_result else {}
            except json.JSONDecodeError:
                analysis_data = {}
                logger.warning("Analysis output could not be parsed as JSON.")

            # Inventory step (optional)
            inventory_result = ""
            if analysis_data.get("requires_inventory_check"):
                inventory_prompt = (
                    "Dựa trên kết quả phân tích sau, hãy kiểm tra tồn kho:\n"
                    f"{analysis_result}\n"
                    "Nếu cần gọi hàm, hãy sử dụng check_inventory_detail như hướng dẫn."
                )
                inventory_result = await _run_agent(self.inventory_runner, inventory_prompt)
                agent_outputs.append({"agent": "inventory_agent", "output": inventory_result})
                logger.debug(f"Inventory Agent output: {inventory_result}")

            # Order step (optional)
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
                    f"{customer_context}"
                    "Nếu thiếu thông tin, trả về thông báo lỗi dạng JSON."
                )
                order_result = await _run_agent(self.order_runner, order_prompt)
                agent_outputs.append({"agent": "order_agent", "output": order_result})
                logger.debug(f"Order output: {order_result}")

            # Consultant step
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
            final_response = await _run_agent(self.consultant_runner, consultant_prompt)
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

            logger.info(f"Pipeline completed successfully for session: {session_id}")
            return result

        except Exception as e:
            logger.error(f"Error in pipeline run: {e}", exc_info=True)
            return {
                "customer_response": f"Xin lỗi, đã xảy ra lỗi khi xử lý yêu cầu của bạn: {str(e)}",
                "status": "error",
                "error": str(e),
            }

    async def run_conversation(self) -> None:
        """Simple interactive CLI that reuses the pipeline run method."""
        logger.info("Starting interactive conversation mode...")
        print("Chào mừng! Nhập 'quit' để thoát.\n")

        while True:
            try:
                user_input = input("Bạn: ")
                if user_input.lower() in {"quit", "exit", "thoát"}:
                    print("Cảm ơn bạn đã sử dụng dịch vụ!")
                    break

                result = await self.run(query=user_input, user_id="interactive_user")
                print(f"\nAgent: {result.get('customer_response', 'Không thể xử lý yêu cầu.')}\n")

            except KeyboardInterrupt:
                print("\nĐã nhận tín hiệu thoát. Tạm biệt!")
                break
            except Exception as e:
                logger.error(f"Error in conversation: {e}")
                print(f"\nĐã xảy ra lỗi: {e}\n")
     
if __name__ == "__main__":
    multi_agents = MultiAgents()

    customer_query = "Tôi muốn mua iPhone 15 Pro Max 256GB màu Titan tự nhiên còn hàng không? Giá bao nhiêu? Nếu có thì tôi muốn đặt hàng ngay."

    asyncio.run(multi_agents.run_conversation())
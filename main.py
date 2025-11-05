import asyncio
from loguru import logger
from src.pipeline_react import MultiAgentsReAct


async def main():
    try:
        multi_agents = MultiAgentsReAct()

        customer_query = "Tôi muốn mua iPhone 15 Pro Max 256GB màu Titan tự nhiên còn hàng không? Giá bao nhiêu? Nếu có thì tôi muốn đặt hàng ngay."

        initial_context = {
            "conversation_id": "conv_001",
            "customer_name": "Nguyễn Văn A",
            "previous_interactions": "Đã từng hỏi về iPad Air."
        }
        
        logger.info(f"Processing customer query: {customer_query}")
        pipeline_output_data = await multi_agents.run(
            customer_query, 
            user_id="user_1",
            initial_context_data=initial_context
        )

        print("\n" + "="*70)
        print(" KẾT QUẢ XỬ LÝ (ReAct Pattern)")
        print("="*70)
        
        if pipeline_output_data.get('status') == 'success':
            print(f"\nTrả lời khách hàng:")
            print(f"   {pipeline_output_data.get('customer_response')}")
            
            print("\n" + "="*70)
            print("CHI TIẾT CÁC BƯỚC:")
            print("="*70)
            
            if pipeline_output_data.get('task1_output'):
                task1 = pipeline_output_data.get('task1_output')
                print(f"\nTask 1 ({task1.get('agent')}):")
                print(f"   {task1.get('output')}")
            
            if pipeline_output_data.get('task2_output'):
                task2 = pipeline_output_data.get('task2_output')
                print(f"\nTask 2 ({task2.get('agent')}):")
                print(f"   {task2.get('output')}")
            
            if pipeline_output_data.get('task3_output'):
                task3 = pipeline_output_data.get('task3_output')
                print(f"\nTask 3 ({task3.get('agent')}):")
                print(f"   {task3.get('output')}")
            
            if pipeline_output_data.get('task4_output'):
                task4 = pipeline_output_data.get('task4_output')
                print(f"\nTask 4 ({task4.get('agent')}):")
                print(f"   {task4.get('output')}")
            
            print(f"\nSession ID: {pipeline_output_data.get('session_id')}")
        else:
            print(f"\nError: {pipeline_output_data.get('error')}")
        
        
        logger.info("ReAct Pipeline execution completed")

    except Exception as e:
        logger.error(f"Lỗi nghiêm trọng trong pipeline: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())

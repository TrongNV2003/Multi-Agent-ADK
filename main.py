import asyncio
from loguru import logger
from src.pipeline_react import MultiAgentsReAct
from src.pipeline_a2a import A2APipeline


# Run the ReAct multi-agent pipeline
async def run_react_pipeline():
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



def print_agent_cards(pipeline: A2APipeline):
    for card in pipeline.list_registered_agents():
        print(f"\n┌─ {card.display_name} ({'v' + card.version})")
        print(f"│  ID: {card.name}")
        print(f"│  Role: {card.role}")
        print(f"│  Capabilities:")
        for cap in card.capabilities:
            print(f"│    • {cap}")
        print(f"│  Input Schema: {list(card.input_schema.keys())}")
        print(f"│  Output Schema: {list(card.output_schema.keys())}")
        if card.endpoint:
            print(f"│  Endpoint: {card.endpoint}")
        print(f"└─")


# Run the A2A pipeline tests
async def run_a2a_pipeline():
    pipeline = A2APipeline()
    
    print_agent_cards(pipeline)
    
    test_queries = [
        {
            "query": "Tôi muốn mua iPhone 15 Pro Max 256GB màu Titan tự nhiên còn hàng không? Giá bao nhiêu?",
            "customer_context": {
                "customer_name": "Nguyễn Văn Trọng",
                "phone": "0123456789"
            }
        },
        {
            "query": "Tôi muốn mua 1 chiếc iPhone 15 Pro Max 256GB màu Titan tự nhiên.",
            "customer_context": {
                "customer_name": "Nguyễn Văn Trọng",
                "phone": "0123456789"
            }
        },
    ]
    
    for i, test_case in enumerate(test_queries, 1):
        print(f"Query: {test_case['query']}")
        print(f"Customer: {test_case['customer_context']}")
        
        try:
            result = await pipeline.run(
                query=test_case['query'],
                customer_context=test_case['customer_context']
            )
            
            print(f"\nFinal Response:\n{result['customer_response']}")
            print(f"\nSession ID: {result['session_id']}")
            print(f"Status: {result['status']}")
            
            print(f"\n{'='*80}")
            print(f"AGENT INTERACTION TRACE")
            for output in result['agent_outputs']:
                print(f"\n[{output['agent'].upper()}]")
                print(f"{output['output']}")
            
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"Error in test case {i}: {e}", exc_info=True)
            continue

if __name__ == "__main__":
    # asyncio.run(run_react_pipeline())
    
    # of
    
    asyncio.run(run_a2a_pipeline())

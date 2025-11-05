"""Tool executor for ReAct pattern - manually parse and execute tool calls."""
import re
import json
import uuid
from typing import Dict, Any, Optional, Callable
from loguru import logger


class ReActToolExecutor:
    """Parse ReAct agent output and execute tools."""
    
    def __init__(self, tools: Dict[str, Callable]):
        """
        Initialize with a mapping of tool names to callables.
        
        Args:
            tools: Dict mapping tool name (str) to tool function (Callable)
        """
        self.tools = tools
        
    def parse_tool_call(self, agent_output: str) -> Optional[Dict[str, Any]]:
        """
        Parse agent output for tool call pattern.
        
        Expected format:
            TOOL_CALL: tool_name
            ARGS: {"arg1": "value1", "arg2": "value2"}
        
        Returns:
            Dict with 'tool_name' and 'args' if found, None otherwise
        """
        tool_match = re.search(r'TOOL_CALL:\s*(\w+)', agent_output, re.IGNORECASE)
        if not tool_match:
            logger.debug("No TOOL_CALL found in agent output")
            return None
        
        tool_name = tool_match.group(1).strip()
        
        args_match = re.search(r'ARGS:\s*(\{.+)', agent_output, re.DOTALL | re.IGNORECASE)
        if not args_match:
            logger.error(f"Found TOOL_CALL but no ARGS for {tool_name}")
            return None
        
        args_section = args_match.group(1).strip()
        
        json_str = self._extract_json_from_text(args_section)
        
        if json_str:
            try:
                args = json.loads(json_str)
                logger.info(f"Parsed tool call: {tool_name} with args keys: {list(args.keys())}")
                return {"tool_name": tool_name, "args": args}
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse args JSON: {e}")
                logger.debug(f"Args string was: {json_str[:300]}")
                return None
        
        logger.error(f"Could not extract valid JSON from ARGS section")
        return None
    
    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """Extract first complete JSON object from text using brace counting."""
        if not text.startswith('{'):
            return None
        
        brace_count = 0
        in_string = False
        escape_next = False
        
        for i, char in enumerate(text):
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        return text[:i+1]
        
        return None
    
    def execute_tool(self, tool_call_info: Dict[str, Any]) -> str:
        """
        Execute the parsed tool call.
        
        Args:
            tool_call_info: Dict with 'tool_name' and 'args'
            
        Returns:
            Tool execution result as string
        """
        tool_name = tool_call_info.get("tool_name")
        args = tool_call_info.get("args", {})
        
        if tool_name not in self.tools:
            error_msg = f"Tool '{tool_name}' not found. Available tools: {list(self.tools.keys())}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})
        
        tool_func = self.tools[tool_name]
        
        try:
            logger.info(f"Executing tool: {tool_name} with args: {args}")
            result = tool_func(**args)
            logger.info(f"Tool execution successful: {result if isinstance(result, str) else result}")
            return result
        except TypeError as e:
            error_msg = f"Tool '{tool_name}' argument error: {e}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})
        except Exception as e:
            error_msg = f"Tool '{tool_name}' execution error: {e}"
            logger.error(error_msg, exc_info=True)
            return json.dumps({"error": error_msg})
    
    def process_agent_output(self, agent_output: str) -> Dict[str, Any]:
        """
        Process agent output: detect tool call, execute if found, return result.
        
        Returns:
            Dict with:
                - tool_called: bool
                - tool_name: str (if called)
                - tool_result: str (if called)
                - original_output: str (agent output)
        """
        result = {
            "tool_called": False,
            "tool_name": None,
            "tool_result": None,
            "original_output": agent_output
        }
        
        tool_call_info = self.parse_tool_call(agent_output)
        
        if tool_call_info:
            result["tool_called"] = True
            result["tool_name"] = tool_call_info["tool_name"]
            result["tool_result"] = self.execute_tool(tool_call_info)
        
        return result


def create_tool_executor_for_pipeline(
    check_inventory_func: Callable,
    create_order_func: Callable
) -> ReActToolExecutor:
    """
    Create a ReActToolExecutor with pipeline tools.
    
    Args:
        check_inventory_func: Function to check inventory
        create_order_func: Function to create order
        
    Returns:
        ReActToolExecutor instance
    """
    tools = {
        "check_inventory_detail": check_inventory_func,
        "create_customer_order": create_order_func
    }
    
    return ReActToolExecutor(tools)

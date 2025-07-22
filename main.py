from langchain_experimental.agents.agent_toolkits import create_csv_agent
from dotenv import load_dotenv
import os
from langchain_core.tools import tool
from typing import Annotated, Dict, Any
from typing_extensions import TypedDict
from langgraph.graph import StateGraph,START,END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt import tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, interrupt
from langchain_community.tools import HumanInputRun
import requests
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from typing import Union
import json
import numpy as np
import pandas as pd
from langchain.agents.agent_types import AgentType
from langchain_openai import ChatOpenAI
import uuid
import os
from io import StringIO


## install MCP chart server, npm install -g @antv/mcp-server-chart
## run MCP chart server, mcp-server-chart --transport sse
from openai import OpenAI
class State(TypedDict):

    messages:Annotated[list,add_messages]


load_dotenv()
llm = ChatOpenAI(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4.1-mini")


UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


## Setup MCP chart
## Global cache of MCP client and agent to avoid reconnecting every call
_mcp_client = None
_chart_agent = None

chartllm = ChatOpenAI(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4.1")
async def async_init_chart_agent():
    global _mcp_client, _chart_agent
    if _mcp_client is None:
        connections: Dict[str, Any] = {
            "chart": {
                "url": "http://localhost:1122/sse",
                "transport": "sse",
            }
        }
        _mcp_client = MultiServerMCPClient(connections)
    tools = await _mcp_client.get_tools()
    _chart_agent = create_react_agent(chartllm, tools)

async def async_generate_chart(chart_config):
    global _chart_agent
    if _chart_agent is None:
        await async_init_chart_agent()

    if isinstance(chart_config, dict):
        chart_content = json.dumps(chart_config)
    else:
        chart_content = chart_config

    # Wrap as a chat message for LLM/MCP call
    message = {
        "role": "user",
        "content": chart_content
    }

    if _chart_agent is None:
        return "Chart agent not initialized"
    response = await _chart_agent.ainvoke({"messages": [message]})
    return response['messages'][-1].content if response.get('messages') else str(response)





jeonse_agent = create_csv_agent(
    llm,
    "Housing_Jeonse_Price_Index_by_Scale__2021.6100.0__20250711213548.csv",
    verbose=True,
    allow_dangerous_code=True,  
    #handle_parsing_errors=True,        
    agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    agent_executor_kwargs = {
        "system_message": (
            "You analysis changes in Jeonse Price, through a price index"
            "Housing type include Apartments, Row Houses, and Detached Houses "
            "Location data are listed under Region(1)"
            "The regions include TheWholeCountry, Seoul, Gyeonggi, Incheon, Busan, Daegu, Gwangju, Daejeon, Ulsan, Sejong, Gangwon, Chungbuk, Chungnam, Jeonbuk, Jeonnam, Gyeongbuk, Gyeongnam, and Jeju"
            "The dates range from 2021.06 to 2025.03"
            "If multiple rows exist, calculate their mean. "
            "Return clean numeric summaries. Do not hallucinate or guess values."
            "If the user request a list, return multiple values and NOT the mean or median of all values"
            "start by finding the region (Region(1)), the isolate to apartment type (Type(1)) and timeframe"
            "If a specific region is not included, assume the user is refering to TheWholeCountry"
        )
    }           
)

## as_tool is specific for agents 
jeonse_agent_tool = jeonse_agent.as_tool(
    arg_types={"input": str},
    name="jeonse_analysis_tool",
    description=
    '''
    Use this tool to analyze CSV data on jeonse Prices between 2021.06 2025.03 on regions of Korea.
    If a specific region is not included, assume the user is refering to TheWholeCountry
    If the user request a list, include the term list in your prompt
    call this if the user ask for price data in relationship to renting or jeonse
    Do not remove information from the user's prompt. INCLUDE the scale (scale 1, scale 2, scale 3, etc), the type (apartment, Row Houses, and Detached Houses) and the region in your prompt
    "Housing type include Apartments, Row Houses, and Detached Houses "
    "Location data are listed under Region(1)"
    "The regions include TheWholeCountry, Seoul, Gyeonggi, Incheon, Busan, Daegu, Gwangju, Daejeon, Ulsan, Sejong, Gangwon, Chungbuk, Chungnam, Jeonbuk, Jeonnam, Gyeongbuk, Gyeongnam, and Jeju"
    "The dates range from 2021.06 to 2025.03"    
    ''',
)

## issue, inconsisenticy in home price csv. Uses both family homes and dwellings for labeling. Need to manually change in csv files
## pre processing of data tool might be nesscary later
home_agent = create_csv_agent(
    llm,
    "Housing_Sales_Price_Index_by_Scale__2021.6100.0__20250711213559.csv",
    verbose=True,
    allow_dangerous_code=True,          
    #handle_parsing_errors=True,
    agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    agent_executor_kwargs = {
        "system_message": (
            "You analysis changes in home prices, through a price index"
            "Housing type include Apartments, Row Houses, and Detached Houses "
            "Location data are listed under Region(1)"
            "The regions include TheWholeCountry, Seoul, Gyeonggi, Incheon, Busan, Daegu, Gwangju, Daejeon, Ulsan, Sejong, Gangwon, Chungbuk, Chungnam, Jeonbuk, Jeonnam, Gyeongbuk, Gyeongnam, and Jeju"
            "The dates range from 2021.06 to 2025.03"
            "If multiple rows exist, calculate their mean. "
            "Return clean numeric summaries. Do not hallucinate or guess values."
            "If the user request a list, return multiple values and NOT the mean or median of all values"
            "start by finding the region (Region(1)), the isolate to apartment type (Type(1)) and timeframe"
            "If a specific region is not included, assume the user is refering to TheWholeCountry"
        )
    }           
)

home_agent_tool = home_agent.as_tool(
    arg_types={"input": str},
    name="home_analysis_tool",
    description=
    '''
    Use this tool to analyze CSV data on home prices between 2021.06 2025.03 on regions of Korea.
    If a specific region is not included, assume the user is refering to TheWholeCountry
    If the user request a list, include the term list in your prompt.
    Call this when the user ask for price data in relationship to home buying or home ownership 
    Do not remove information from the user's prompt. INCLUDE the scale (scale 1, scale 2, scale 3, etc), the type (apartment, Row Houses, and Detached Houses) and the region in your prompt
    "Housing type include Apartments, Row Houses, and Detached Houses "
    "Location data are listed under Region(1)"
    "The regions include TheWholeCountry, Seoul, Gyeonggi, Incheon, Busan, Daegu, Gwangju, Daejeon, Ulsan, Sejong, Gangwon, Chungbuk, Chungnam, Jeonbuk, Jeonnam, Gyeongbuk, Gyeongnam, and Jeju"
    "The dates range from 2021.06 to 2025.03"
    ''',
)


# # human-in-the-loop intervention
# human_assistant = HumanInputRun(
#     name="human_assistant_tool",
#     description=
#     """
#     Use this tool **only** when the user request you to add information to the 
#     graph AND you cannot find said information using any other tool, such as the search tool.
#     """
# )


## MCP chart generation tool Wrapper 
@tool(
        description="Generate charts or graphs from structured data specifying type, data points, and titles. The link returned by the tool should ALWAYS BE OUTPUTTED AND GIVE TO THE USER" 

)
def generate_chart_tool(chart_config: Union[str, dict]) -> str:
    if isinstance(chart_config, str):
        chart_config = json.loads(chart_config)  # parse JSON if string input

    # Call async chart generator with structured config
    return asyncio.run(async_generate_chart(chart_config))


@tool(
    description='''
Creates a new CSV from provided JSON data or raw CSV text. 
        Input: a JSON string with keys 'data' (list of objects) or 'csv_string' (CSV text), 
        and optional 'filename'. 
        Returns the relative download URL.
'''
        
)
def create_csv_file_tool(payload: str) -> str:
    """
    payload JSON schema:
      { 
        "data": [ {col: val, ...}, ... ] or
        "csv_string": "col1,col2\nv1,v2\n...",
        "filename": "my_output.csv"  (optional)
      }
    """
    # parse
    obj = __import__("json").loads(payload)
    # choose filename
    fname = obj.get("filename") or f"output_{uuid.uuid4().hex}.csv"
    # build dataframe
    if "data" in obj:
        df = pd.DataFrame(obj["data"])
    elif "csv_string" in obj:
        df = pd.read_csv(StringIO(obj["csv_string"]))
    else:
        raise ValueError("Must provide either 'data' or 'csv_string'")
    # write out
    out_path = os.path.join(UPLOAD_DIR, fname)
    df.to_csv(out_path, index=False)
    # return the download endpoint (served by app.py)
    return f"/download/{fname}"



tools = [jeonse_agent_tool, 
        home_agent_tool, 
        generate_chart_tool,
        create_csv_file_tool]
    
def build_agent_graph(tools, memory):

    llm_with_tool = llm.bind_tools(tools)

    # memory = MemorySaver()

    ## Node definition
    def main_agent(state:State):
        return {"messages":[llm_with_tool.invoke(state["messages"])]}

    ## Graph
    builder=StateGraph(State)
    builder.add_node("main_agent",main_agent)
    builder.add_node("tools",ToolNode(tools))

    ## Add Edges
    builder.add_edge(START, "main_agent")
    builder.add_conditional_edges(
        "main_agent",
        # If the latest message (result) from assistant is a tool call -> tools_condition routes to tools
        # If the latest message (result) from assistant is a not a tool call -> tools_condition routes to END
        tools_condition
    )
    builder.add_edge("tools","main_agent")

    ## compile the graph, keeps memory
    graph=builder.compile(checkpointer=memory)

    return graph





# config = {"configurable":{"thread_id":"1"}}
# memory = MemorySaver()
# graph = build_agent_graph(tools, memory)
# response = graph.invoke({"messages": "give me a csv file of just seoul jeonse data in 2024 for apartments "}, config=config)

# #response = graph.invoke({"messages": "give me a chart use the generate chart tool. x axis is letter, y axis is number. x is [a , b , c]. y axis  is [1 , 2 , 3]. title is abcChart. and chart type is a graph  "}, config=config)
# for m in response['messages']:
#      m.pretty_print()


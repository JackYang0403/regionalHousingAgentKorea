from langchain_experimental.agents.agent_toolkits import create_csv_agent
from langchain_openai import ChatOpenAI
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



## install MCP chart server, npm install -g @antv/mcp-server-chart
## run MCP chart server, mcp-server-chart --transport sse

class State(TypedDict):

    messages:Annotated[list,add_messages]



load_dotenv()
openai_key = os.getenv("OPENAI_API_KEY")
llm = ChatOpenAI(api_key=openai_key, model="gpt-4")

## Setup MCP chart
## Global cache of MCP client and agent to avoid reconnecting every call
_mcp_client = None
_chart_agent = None

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
    _chart_agent = create_react_agent("openai:gpt-4.1", tools)

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



    

rent_agent = create_csv_agent(
    llm,
    "medianAskingRent_All.csv",
    verbose=True,
    allow_dangerous_code=True,           # allows the agent to run Python code
    handle_parsing_errors=True           # retries if LLM output breaks
)

## as_tool is specific for agents 
rent_agent_tool = rent_agent.as_tool(
    arg_types={"input": str},
    name="rent_cost_analysis_tool",
    description=
    '''
    Use this tool to analyze CSV data on median asking rent between Jan 2010 and May 2025 on various neighborhoods.
    YOU HAVE TO INCLUDE whether the area is a Neighborhood (listed as areaName in the csv file) or Borough in your call to the tool. If the name of the area is not Brooklyn, Manhattan, Staten Island, Queens, or Bronx, assume that it is a Neighborhood. 
    Ask in natural English, e.g., 'What was the median asking rent in Harlem in 2023?
    ''',
)

## issue, inconsisenticy in home price csv. Uses both family homes and dwellings for labeling. Need to manually change in csv files
## pre processing of data tool might be nesscary later
home_price_agent = create_csv_agent(
    llm,
    "DOF__Summary_of_Neighborhood_Sales_by_Neighborhood_Citywide_by_Borough_20250704.csv",
    verbose=True,
    allow_dangerous_code=True,           # allows the agent to run Python code
    handle_parsing_errors=True           # retries if LLM output breaks
)

home_price_agent_tool = home_price_agent.as_tool(
    arg_types={"input": str},
    name="home_price_cost_analysis_tool",
    description=
    '''
    Use this tool to analyze CSV data on median sale price, lowest sale price, highest sale price, and/or average sale price
           of a one, two, or three family homes bewteen 2010 and 2024 on various neighborhoods. The data are recorded by 
           neighborhood, year, and number of family. 
    INCLUDE whether the area is a Neighborhood or Borough in your call to the tool. If the name of the area is not Brooklyn, Manhattan, Staten Island, Queens, or Bronx, assume that it is a Neighborhood. 
    Be specific about whether you want a list of data or statistics (median, mean, etc)
    ''',
)

@tool(
        description=
        """
        Calculate monthly mortgage payment using the amortization formula.

        Parameters:
            home_price (float): Total cost of the home.
            down_payment (float): Initial down payment (in dollars).
            annual_interest_rate (float): Annual interest rate in percent (e.g., 6.5 for 6.5%).
            loan_term_years (int): Length of the loan in years.

        Returns:
            float: Monthly mortgage payment.
        """
        
)
def calculate_monthly_mortgage(home_price :float, down_payment :float , 
                               annual_interest_rate :float, loan_term_years : int) -> float:

    loan_amount = home_price - down_payment
    monthly_interest_rate = annual_interest_rate / 100 / 12
    number_of_payments = loan_term_years * 12

    if monthly_interest_rate == 0:
        return loan_amount / number_of_payments  # No interest

    monthly_payment = loan_amount * (
        monthly_interest_rate * (1 + monthly_interest_rate) ** number_of_payments
    ) / ((1 + monthly_interest_rate) ** number_of_payments - 1)

    return monthly_payment


## human-in-the-loop intervention
human_assistant_tool_mortage = HumanInputRun(
    name="human_assistant_tool",
    description=
    """
    Use this tool **only** when attempting to calculate a monthly mortgage payment using the `calculate_monthly_mortgage` tool,
    but one or more of the required inputs is missing or unclear.

    Required inputs for `calculate_monthly_mortgage`:
    - home price
    - down payment
    - annual interest rate (as a percentage)
    - loan term in years
    Example use case: You know the home price, but the user did not specify the interest rate or loan term.
    Ask the human a direct follow-up question to retrieve the missing values.
    Do not use this tool for general questions or other types of information.
    """
)

## MCP chart generation tool Wrapper 
@tool(
        description="Generate charts or graphs from structured data specifying type, data points, and titles."
)
def generate_chart_tool(chart_config: Union[str, dict]) -> str:
    if isinstance(chart_config, str):
        chart_config = json.loads(chart_config)  # parse JSON if string input

    # Call async chart generator with structured config
    return asyncio.run(async_generate_chart(chart_config))

    

tools = [rent_agent_tool, home_price_agent_tool, 
         calculate_monthly_mortgage, 
         human_assistant_tool_mortage, 
         generate_chart_tool]

llm_with_tool = llm.bind_tools(tools)

memory = MemorySaver()

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



# ## test 
# # response = graph.invoke({'messages': 'list the median sale prices of a one family home in Bensonhurst every year from 2015 to 2022'}, config=config)
# # response = graph.invoke({'messages': 'Make a chart or graph for the sale prices '}, config=config)
# # # # response = graph.invoke({'messages': 'generate a different type of chart of graph for the same data '}, config=config)
# # # # response = graph.invoke({'messages': 'What would be the monthly payment on the house be with a 30 year mortgage?'}, config=config)
# # # # print(response['messages'][-1].content)

# for m in response['messages']:
#     m.pretty_print()

## user ID
# config = {"configurable":{"thread_id":"1"}}

# response = graph.invoke({"messages": "What is the median sale cost of a home in Bensonhurst during 2014 "}, config=config)

# for m in response['messages']:
#      m.pretty_print()


# messages = [m.content for m in response['messages']]
# print(messages)

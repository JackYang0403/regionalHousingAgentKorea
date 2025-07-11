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

load_dotenv()
openai_key = os.getenv("OPENAI_API_KEY")
llm = ChatOpenAI(api_key=openai_key, model="gpt-4")

rent_agent = create_csv_agent(
    llm,
    "rent_Seoul_2024.csv",
    verbose=True,
    allow_dangerous_code=True,           # allows the agent to run Python code
    handle_parsing_errors=True,      
    pd_kwargs={"encoding": "EUC-KR"}
)

res = rent_agent.invoke("what is the average monthly rent in 종로구? ")
print(res)
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
import asyncio

## run MCP server, mcp-server-chart --transport sse 
async def main():
    client = MultiServerMCPClient(
        {
            # Your mcp-server-chart instance running locally on port 1122 with SSE transport
            # "chart": {
            #     "url": "http://localhost:1122/sse",
            #     "transport": "sse",
            # }
            "google_maps": {
                "command": "mcp-server-google-maps",
                "transport": "stdio",
                "args": [],
            }
        }
    )
    
    # Fetch tools from server (this will let the agent know what the chart server can do)
    tools = await client.get_tools()
    
    # Print the tools for debugging — this shows what functions are available
    print("Available tools:", tools)
    
    # Create an agent with GPT-4.1 and the available tools
    agent = create_react_agent("openai:gpt-4.1", tools)
    
    # Send a message asking the chart server to generate a random chart
    map_response = await agent.ainvoke({"messages": "Find coffee shops near Seoul Station and give me reviews"})

    print("Google Maps server response:", map_response)

if __name__ == "__main__":
    asyncio.run(main())
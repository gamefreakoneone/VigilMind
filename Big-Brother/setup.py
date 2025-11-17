# openai_ping.py
import os
import asyncio
from dotenv import load_dotenv
from openai import OpenAI

from agents import Agent, Runner, WebSearchTool, function_tool

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

web_checker_agent = Agent(
    name="Parental Web Content Analyzer",
    tools=[WebSearchTool()],
    model="gpt-5-mini",
)

async def main():
    result = await Runner.run(
        web_checker_agent,
        "Finish the sentence: Bitches love my openai agent, because it can do the following: ",
    )

    # RunResult.final_output is the actual LLM output string
    print(result.final_output)

if __name__ == "__main__":
    asyncio.run(main())

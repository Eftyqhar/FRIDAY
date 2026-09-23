"""
Example: Autonomous web scraping and structured extraction using Gemini + Playwright.
Extracts quotes and authors from http://quotes.toscrape.com
"""

import sys
import asyncio

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from agent import AutonomousBrowserAgent
from config import AgentConfig

async def main():
    cfg = AgentConfig()
    cfg.headless = True
    
    agent = AutonomousBrowserAgent(cfg)
    task = (
        "Navigate to https://quotes.toscrape.com, find the top 3 quotes and their authors, "
        "and extract them into a clean JSON list with 'quote' and 'author' keys."
    )
    
    result = await agent.run(task=task, start_url="https://quotes.toscrape.com")
    print("\nResult:")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())

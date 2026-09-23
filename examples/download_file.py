"""
Example: Autonomous portal navigation and file downloading.
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
    cfg.headless = False  # Set to headed so the user can watch the download happen live
    
    agent = AutonomousBrowserAgent(cfg)
    task = (
        "Go to https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf, "
        "and download the sample PDF file to the downloads folder."
    )
    
    result = await agent.run(task=task, start_url="https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf")
    print("\nResult:")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())

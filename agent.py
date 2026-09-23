import re
import json
import asyncio
from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from google import genai
from google.genai import types

from config import config, AgentConfig
from actions import AgentAction
from browser_manager import BrowserManager
from dom_annotator import DOMAnnotator

console = Console()

SYSTEM_PROMPT = """
You are FRIDAY, an autonomous AI browser assistant. Your goal is to navigate web applications and execute user instructions autonomously.

You perceive the web page through:
1. Current Page Title & URL.
2. Visible Headings and page text content.
3. An indexed table of visible interactive elements (buttons, inputs, links, dropdowns) with numeric IDs: [1], [2], [3], etc.
4. History of recent actions taken.

Instructions:
- Carefully analyze the current page state, text content, and recent actions.
- Pick the single most logical next step towards the user's goal.
- For clicking buttons, links, or inputs, specify `element_id` matching the table ID.
- When typing into search boxes, forms, or inputs:
  - Specify `element_id` and the `text` to type.
  - If it is a search box or input where Enter submits, set `press_enter: true`.
- If you need to view more content down the page, use `action: "scroll"` with `direction: "down"`.
- If you encounter a cookie consent banner or modal popup, dismiss or accept it first.
- When the goal is completed:
  - Call `action: "complete"`.
  - Provide a concise `summary` of what was accomplished.
  - If information was requested to be extracted, include it in `extracted_data`.
- If blocked or unable to proceed, call `action: "fail"` with `summary`.

Output Format:
You MUST respond with a valid JSON object matching this schema:
{
  "thought": "Your reasoning here",
  "action": "click" | "type" | "press_key" | "select_option" | "scroll" | "navigate" | "wait" | "complete" | "fail",
  "element_id": 1,
  "text": "text to type or key to press (optional)",
  "clear_before": true,
  "press_enter": false,
  "option": "dropdown option (optional)",
  "url": "url to navigate to (optional)",
  "direction": "down",
  "amount": 500,
  "seconds": 2.0,
  "extracted_data": "extracted result (optional)",
  "summary": "completion or failure message (optional)"
}
"""

class AutonomousBrowserAgent:
    """Core autonomous agent coordinating perception, reasoning, and browser actions."""

    def __init__(self, cfg: Optional[AgentConfig] = None):
        self.cfg = cfg or config
        if not self.cfg.api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set! Please set it in your environment or in a .env file."
            )

        http_opts = types.HttpOptions(base_url=self.cfg.base_url) if self.cfg.base_url else None
        self.client = genai.Client(api_key=self.cfg.api_key, http_options=http_opts)
        self.browser_manager = BrowserManager(self.cfg)
        self.action_history: List[Dict[str, Any]] = []

    async def run(self, task: str, start_url: Optional[str] = None) -> Dict[str, Any]:
        """Executes a task autonomously in the browser until completion or max steps."""
        browser_info = self.cfg.browser_executable or "Chromium"
        mode_info = "Text-Only DOM Mode" if self.cfg.text_only_mode else "Vision + DOM Mode"
        info_panel = (
            f"[bold cyan]Task:[/bold cyan] {task}\n"
            f"[dim]Endpoint:[/dim] {self.cfg.base_url or 'Default Google API'}\n"
            f"[dim]Browser:[/dim] {browser_info}\n"
            f"[dim]Mode:[/dim] [yellow]{mode_info}[/yellow]"
        )
        console.print(Panel(info_panel, title="🤖 FRIDAY Autonomous Browser Assistant", border_style="cyan"))

        await self.browser_manager.start()

        # Initial navigation if provided
        if start_url:
            console.print(f"[dim]Navigating to initial URL: {start_url}[/dim]")
            await self.browser_manager.navigate(start_url)
        elif not self.browser_manager.page.url or self.browser_manager.page.url == "about:blank":
            await self.browser_manager.navigate("https://www.google.com")

        step = 0
        final_result = {"status": "in_progress", "steps_taken": 0, "summary": None, "extracted_data": None}

        try:
            while step < self.cfg.max_steps:
                step += 1
                console.rule(f"[bold yellow]Step {step} / {self.cfg.max_steps}[/bold yellow]")

                # 1. Observe (Perception)
                screenshot_bytes, elements, page_summary = await self.browser_manager.capture_state(step)
                current_url = self.browser_manager.page.url
                page_title = await self.browser_manager.page.title()
                elements_text = DOMAnnotator.format_elements_for_prompt(elements)

                console.print(f"[dim]Page:[/dim] {page_title} ([underline]{current_url}[/underline])")
                if page_summary.get("headings"):
                    console.print(f"[dim]Headings:[/dim] {page_summary['headings']}")
                console.print(f"[dim]Visible interactive elements found:[/dim] {len(elements)}")

                # 2. Reason (Text or Multimodal Gemini Call)
                action = await self._decide_next_action(
                    task=task,
                    step=step,
                    current_url=current_url,
                    page_title=page_title,
                    elements_text=elements_text,
                    page_summary=page_summary,
                    screenshot_bytes=screenshot_bytes
                )

                console.print(f"[bold green]Thought:[/bold green] {action.thought}")
                console.print(f"[bold magenta]Action:[/bold magenta] {action.action} "
                              f"(element_id={action.element_id}, text={action.text!r}, url={action.url!r})")

                # 3. Act (Execution & Self-Healing)
                success = await self._execute_action(action)

                # Record to history
                self.action_history.append({
                    "step": step,
                    "thought": action.thought,
                    "action": action.action,
                    "element_id": action.element_id,
                    "success": success
                })

                # Check termination
                if action.action == "complete":
                    final_result["status"] = "success"
                    final_result["summary"] = action.summary or "Task finished successfully."
                    final_result["extracted_data"] = action.extracted_data
                    console.print(Panel(
                        f"[bold green]Task Succeeded![/bold green]\n\n"
                        f"[bold]Summary:[/bold] {final_result['summary']}\n"
                        + (f"\n[bold]Extracted Data:[/bold]\n{final_result['extracted_data']}" if final_result['extracted_data'] else ""),
                        title="🎉 Completion",
                        border_style="green"
                    ))
                    break

                if action.action == "fail":
                    final_result["status"] = "failed"
                    final_result["summary"] = action.summary or "Agent reported failure."
                    console.print(Panel(f"[bold red]Task Failed:[/bold red] {final_result['summary']}", title="❌ Failure", border_style="red"))
                    break

                await asyncio.sleep(1.0)

            if step >= self.cfg.max_steps and final_result["status"] == "in_progress":
                final_result["status"] = "timeout"
                final_result["summary"] = f"Reached maximum allowed steps ({self.cfg.max_steps})."
                console.print(Panel(f"[bold yellow]Max steps reached without explicit completion.[/bold yellow]", title="⚠️ Timeout", border_style="yellow"))

        finally:
            final_result["steps_taken"] = step
            final_result["downloaded_files"] = [str(p) for p in self.browser_manager.downloaded_files]
            await self.browser_manager.stop()

        return final_result

    async def _decide_next_action(
        self,
        task: str,
        step: int,
        current_url: str,
        page_title: str,
        elements_text: str,
        page_summary: Dict[str, str],
        screenshot_bytes: bytes
    ) -> AgentAction:
        """Queries Gemini with the current DOM state, using pure text for text-only models."""
        history_summary = ""
        if self.action_history:
            recent = self.action_history[-4:]
            history_summary = "Recent actions:\n" + "\n".join(
                [f"- Step {h['step']}: {h['action']} (element {h['element_id']}) -> {'success' if h['success'] else 'failed'}" for h in recent]
            )

        headings_info = f"Visible Headings:\n{page_summary.get('headings', 'None')}\n" if page_summary.get("headings") else ""
        content_info = f"Page Text Excerpt:\n{page_summary.get('content', 'None')}\n" if page_summary.get("content") else ""

        user_content = f"""
Current Task: {task}
Step Number: {step}
Current URL: {current_url}
Page Title: {page_title}

{headings_info}
{content_info}
{history_summary}

Visible Interactive Elements Table:
{elements_text}

Determine the single next action to take towards completing the task. Respond with a single valid JSON object.
"""

        # Choose contents: text-only vs multimodal
        contents = [user_content]
        if not self.cfg.text_only_mode and screenshot_bytes:
            contents.insert(0, types.Part.from_bytes(data=screenshot_bytes, mime_type="image/png"))

        try:
            response = self.client.models.generate_content(
                model=self.cfg.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.2,
                )
            )

            raw_text = response.text.strip()
            # Clean possible markdown wrapping
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                raw_text = raw_text.split("```")[1].split("```")[0].strip()

            action = AgentAction.model_validate_json(raw_text)
            return action

        except Exception as e:
            console.print(f"[bold red]Gemini Decision Error:[/bold red] {e}")
            return AgentAction(
                thought=f"Error parsing Gemini response ({e}). Retrying with wait.",
                action="wait",
                seconds=2.0
            )

    async def _execute_action(self, action: AgentAction) -> bool:
        """Dispatches action to the browser manager."""
        bm = self.browser_manager

        if action.action == "click" or action.action == "download_click":
            return await bm.execute_click(
                element_id=action.element_id,
                x=action.coordinate_x,
                y=action.coordinate_y
            )

        elif action.action == "type":
            text = action.text or ""
            return await bm.execute_type(
                element_id=action.element_id,
                text=text,
                clear_before=action.clear_before,
                press_enter=action.press_enter
            )

        elif action.action == "press_key":
            key = action.text or "Enter"
            return await bm.execute_press_key(key)

        elif action.action == "select_option":
            if action.element_id and action.option:
                return await bm.execute_select_option(action.element_id, action.option)
            return False

        elif action.action == "scroll":
            return await bm.execute_scroll(
                direction=action.direction or "down",
                amount=action.amount or 500
            )

        elif action.action == "navigate":
            if action.url:
                return await bm.navigate(action.url)
            return False

        elif action.action == "wait":
            return await bm.wait(action.seconds or 2.0)

        elif action.action in ("extract_data", "complete", "fail"):
            return True

        return False

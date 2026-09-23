from typing import Optional, Literal
from pydantic import BaseModel, Field

ActionType = Literal[
    "click",
    "type",
    "press_key",
    "select_option",
    "scroll",
    "navigate",
    "wait",
    "download_click",
    "extract_data",
    "complete",
    "fail"
]

class AgentAction(BaseModel):
    """Structured action decided by the agent's reasoning loop."""
    thought: str = Field(description="Step-by-step reasoning explaining why this action is chosen.")
    action: ActionType = Field(description="The action type to execute.")
    
    # Target identifiers
    element_id: Optional[int] = Field(default=None, description="The integer label ID [1], [2] of the interactive element.")
    selector: Optional[str] = Field(default=None, description="CSS or XPath selector if known or used for self-healing.")
    coordinate_x: Optional[int] = Field(default=None, description="X viewport coordinate for visual click fallback.")
    coordinate_y: Optional[int] = Field(default=None, description="Y viewport coordinate for visual click fallback.")
    
    # Action arguments
    text: Optional[str] = Field(default=None, description="Text to input when typing or key name for press_key.")
    clear_before: bool = Field(default=True, description="Whether to clear existing text before typing.")
    press_enter: bool = Field(default=False, description="Whether to press Enter key immediately after typing.")
    option: Optional[str] = Field(default=None, description="Option label or value to select in a <select> dropdown.")
    url: Optional[str] = Field(default=None, description="Target URL for navigation.")
    direction: Optional[Literal["up", "down"]] = Field(default="down", description="Scroll direction.")
    amount: Optional[int] = Field(default=500, description="Scroll distance in pixels.")
    seconds: Optional[float] = Field(default=2.0, description="Wait duration in seconds.")
    
    # Completion and extraction
    extracted_data: Optional[str] = Field(default=None, description="Extracted content or answer when extracting data.")
    summary: Optional[str] = Field(default=None, description="Final summary of the completed task or failure explanation.")

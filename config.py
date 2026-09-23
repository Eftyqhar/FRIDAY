import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

def detect_brave_path() -> Optional[str]:
    """Auto-detects Brave browser executable on Windows, macOS, and Linux."""
    custom_path = os.getenv("BRAVE_PATH") or os.getenv("BROWSER_PATH")
    if custom_path and os.path.exists(custom_path):
        return custom_path

    candidate_paths = []
    if sys.platform == "win32":
        local_app_data = os.getenv("LOCALAPPDATA", "")
        candidate_paths = [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
            os.path.join(local_app_data, r"BraveSoftware\Brave-Browser\Application\brave.exe") if local_app_data else ""
        ]
    elif sys.platform == "darwin":
        candidate_paths = [
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
        ]
    else:
        candidate_paths = [
            "/usr/bin/brave-browser",
            "/usr/bin/brave",
            "/snap/bin/brave"
        ]

    for path in candidate_paths:
        if path and os.path.exists(path):
            return path
    return None

def detect_brave_user_data() -> Optional[str]:
    """Auto-detects the default Brave User Data folder."""
    custom_dir = os.getenv("BRAVE_USER_DATA_DIR")
    if custom_dir and os.path.exists(custom_dir):
        return custom_dir

    if sys.platform == "win32":
        local_app_data = os.getenv("LOCALAPPDATA", "")
        if local_app_data:
            p = os.path.join(local_app_data, r"BraveSoftware\Brave-Browser\User Data")
            if os.path.exists(p):
                return p
    elif sys.platform == "darwin":
        p = os.path.expanduser("~/Library/Application Support/BraveSoftware/Brave-Browser")
        if os.path.exists(p):
            return p
    else:
        p = os.path.expanduser("~/.config/BraveSoftware/Brave-Browser")
        if os.path.exists(p):
            return p
    return None

@dataclass
class AgentConfig:
    # Model Configuration
    api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    model_name: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    base_url: str = field(default_factory=lambda: os.getenv("GEMINI_BASE_URL", "https://api.hcnsec.cn").rstrip("/"))
    text_only_mode: bool = field(default_factory=lambda: os.getenv("TEXT_ONLY_MODE", "true").lower() in ("true", "1", "yes"))
    
    # Browser & Profile Settings
    browser_type: str = field(default_factory=lambda: os.getenv("BROWSER_TYPE", "brave"))
    browser_executable: Optional[str] = field(default_factory=detect_brave_path)
    use_existing_profile: bool = field(default_factory=lambda: os.getenv("USE_EXISTING_PROFILE", "true").lower() in ("true", "1", "yes"))
    isolated_profile: bool = field(default_factory=lambda: os.getenv("ISOLATED_PROFILE", "false").lower() in ("true", "1", "yes"))
    brave_user_data_dir: Optional[str] = field(default_factory=detect_brave_user_data)
    profile_name: str = field(default_factory=lambda: os.getenv("BRAVE_PROFILE_NAME", "Default"))
    cdp_url: Optional[str] = field(default_factory=lambda: os.getenv("CDP_URL", None))

    headless: bool = field(default_factory=lambda: os.getenv("HEADLESS", "false").lower() in ("true", "1", "yes"))
    viewport_width: int = field(default_factory=lambda: int(os.getenv("VIEWPORT_WIDTH", "1280")))
    viewport_height: int = field(default_factory=lambda: int(os.getenv("VIEWPORT_HEIGHT", "800")))
    slow_mo_ms: int = field(default_factory=lambda: int(os.getenv("SLOW_MO_MS", "300")))
    
    # Execution Limits
    max_steps: int = field(default_factory=lambda: int(os.getenv("MAX_STEPS", "25")))
    timeout_ms: int = 30000
    
    # Storage Paths
    work_dir: Path = field(default_factory=lambda: Path(os.getcwd()))
    persistent_profile_dir: Path = field(init=False)
    downloads_dir: Path = field(init=False)
    screenshots_dir: Path = field(init=False)
    traces_dir: Path = field(init=False)
    
    def __post_init__(self):
        self.persistent_profile_dir = self.work_dir / ".brave_profile"
        self.persistent_profile_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_dir = self.work_dir / "downloads"
        self.screenshots_dir = self.work_dir / "screenshots"
        self.traces_dir = self.work_dir / "traces"
        
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.traces_dir.mkdir(parents=True, exist_ok=True)

config = AgentConfig()

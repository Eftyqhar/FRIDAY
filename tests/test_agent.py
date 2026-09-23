import sys
import asyncio
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from browser_manager import BrowserManager
from dom_annotator import DOMAnnotator
from config import AgentConfig

# Minimal local HTML test fixture to verify interactions without external network dependencies
TEST_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Autonomous Browser Test Page</title>
    <style>
        body { font-family: sans-serif; padding: 20px; }
        .box { margin-bottom: 15px; }
        #result { margin-top: 20px; font-weight: bold; color: green; }
    </style>
</head>
<body>
    <h1>Automated Test Form</h1>
    <div class="box">
        <label for="username">Username:</label>
        <input id="username" type="text" placeholder="Enter username" />
    </div>
    <div class="box">
        <label for="role">Role:</label>
        <select id="role">
            <option value="user">Standard User</option>
            <option value="admin">Administrator</option>
        </select>
    </div>
    <div class="box">
        <button id="submit-btn" onclick="submitForm()">Submit Data</button>
    </div>
    <div id="result">Waiting for action...</div>

    <script>
        function submitForm() {
            const user = document.getElementById('username').value;
            const role = document.getElementById('role').value;
            document.getElementById('result').innerText = `Success: Submitted ${user} with role ${role}`;
        }
    </script>
</body>
</html>
"""

async def run_smoke_test():
    """Runs an end-to-end smoke test verifying Playwright, DOM annotation, typing, and clicking."""
    print("=" * 60)
    print(" Running Autonomous Browser Smoke Test...")
    print("=" * 60)

    cfg = AgentConfig()
    cfg.headless = True
    cfg.isolated_profile = True
    bm = BrowserManager(cfg)


    # Write temporary local HTML fixture
    test_fixture = cfg.work_dir / "test_fixture.html"
    test_fixture.write_text(TEST_HTML, encoding="utf-8")

    try:
        # 1. Start browser
        print("[1/5] Starting Playwright Chromium...")
        await bm.start()
        print("  [OK] Browser started successfully.")

        # 2. Navigate to local page
        file_url = f"file:///{test_fixture.resolve().as_posix()}"
        print(f"[2/5] Navigating to test page: {file_url}")
        success = await bm.navigate(file_url)
        assert success, "Navigation failed!"
        print("  [OK] Navigation confirmed.")

        # 3. DOM Annotation, Page Summary & Screenshot
        print("[3/5] Annotating DOM elements, extracting page summary and capturing screenshot...")
        screenshot_bytes, elements, page_summary = await bm.capture_state(step_num=1)
        assert len(screenshot_bytes) > 0, "Screenshot capture failed!"
        assert len(elements) >= 3, f"Expected at least 3 interactive elements, got {len(elements)}"
        assert "Automated Test Form" in page_summary.get("headings", ""), "Failed to extract page headings!"
        print(f"  [OK] Found {len(elements)} interactive elements and extracted page headings.")
        print(f"  Page Headings: {page_summary.get('headings')}")
        print("  Sample element table:")
        print(DOMAnnotator.format_elements_for_prompt(elements[:3]))


        # Find the input and button
        input_el = next((el for el in elements if el.tag == "input"), None)
        button_el = next((el for el in elements if el.tag == "button"), None)
        assert input_el is not None, "Input element not found in DOM harvester!"
        assert button_el is not None, "Button element not found in DOM harvester!"

        # 4. Execute Type Action
        print(f"[4/5] Typing 'AgentTester' into input field [ID {input_el.id}]...")
        type_ok = await bm.execute_type(element_id=input_el.id, text="AgentTester", clear_before=True)
        assert type_ok, "Typing failed!"
        print("  [OK] Text typed successfully.")

        # 5. Execute Click Action
        print(f"[5/5] Clicking submit button [ID {button_el.id}]...")
        click_ok = await bm.execute_click(element_id=button_el.id)
        assert click_ok, "Click failed!"
        
        # Verify DOM updated
        result_text = await bm.page.inner_text("#result")
        print(f"  [OK] Result element text: {result_text}")
        assert "Success: Submitted AgentTester" in result_text, f"Unexpected result: {result_text}"

        print("\n>>> SMOKE TEST PASSED! All core automation components are functioning perfectly.")

    finally:
        await bm.stop()
        if test_fixture.exists():
            test_fixture.unlink()

if __name__ == "__main__":
    asyncio.run(run_smoke_test())


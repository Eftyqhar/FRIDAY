import json
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

DOM_INJECT_JS = """
(() => {
    // Clean up previous agent overlays
    const existingContainer = document.getElementById('__agent_overlay_container__');
    if (existingContainer) existingContainer.remove();
    document.querySelectorAll('[data-agent-id]').forEach(el => el.removeAttribute('data-agent-id'));

    const overlayContainer = document.createElement('div');
    overlayContainer.id = '__agent_overlay_container__';
    overlayContainer.style.position = 'fixed';
    overlayContainer.style.top = '0';
    overlayContainer.style.left = '0';
    overlayContainer.style.width = '100vw';
    overlayContainer.style.height = '100vh';
    overlayContainer.style.pointerEvents = 'none';
    overlayContainer.style.zIndex = '2147483647';
    document.documentElement.appendChild(overlayContainer);

    const interactiveSelectors = [
        'a[href]', 'button', 'input', 'textarea', 'select',
        '[role="button"]', '[role="link"]', '[role="checkbox"]', '[role="menuitem"]',
        '[role="tab"]', '[role="combobox"]', '[role="switch"]', '[contenteditable="true"]',
        '[tabindex]:not([tabindex="-1"])'
    ];

    const elements = Array.from(document.querySelectorAll(interactiveSelectors.join(',')));
    
    // Also include elements with pointer cursor or click handlers
    const allElements = document.querySelectorAll('div, span, li, p, svg');
    for (let i = 0; i < Math.min(allElements.length, 300); i++) {
        const el = allElements[i];
        if (el.onclick || window.getComputedStyle(el).cursor === 'pointer') {
            if (!elements.includes(el)) elements.push(el);
        }
    }

    const items = [];
    let idCounter = 1;

    for (const el of elements) {
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);

        // Check visibility and dimensions
        if (
            rect.width <= 0 || rect.height <= 0 ||
            style.visibility === 'hidden' ||
            style.display === 'none' ||
            style.opacity === '0' ||
            rect.bottom < 0 || rect.top > window.innerHeight ||
            rect.right < 0 || rect.left > window.innerWidth
        ) {
            continue;
        }

        // Tag the element
        const currentId = idCounter++;
        el.setAttribute('data-agent-id', currentId.toString());

        // Extract meaningful text
        let text = (el.innerText || el.textContent || '').trim();
        if (!text && el.placeholder) text = `placeholder: "${el.placeholder}"`;
        if (!text && el.value) text = `val: "${el.value}"`;
        if (!text && el.getAttribute('aria-label')) text = `aria: "${el.getAttribute('aria-label')}"`;
        if (!text && el.title) text = `title: "${el.title}"`;
        if (!text && el.alt) text = `alt: "${el.alt}"`;
        if (text.length > 80) text = text.substring(0, 77) + '...';

        // Create visible badge overlay
        const badge = document.createElement('div');
        badge.innerText = currentId.toString();
        badge.style.position = 'absolute';
        badge.style.top = `${Math.max(0, rect.top)}px`;
        badge.style.left = `${Math.max(0, rect.left)}px`;
        badge.style.backgroundColor = '#ffeb3b';
        badge.style.color = '#000000';
        badge.style.border = '1px solid #d32f2f';
        badge.style.borderRadius = '3px';
        badge.style.padding = '1px 4px';
        badge.style.fontSize = '11px';
        badge.style.fontFamily = 'monospace';
        badge.style.fontWeight = 'bold';
        badge.style.lineHeight = '12px';
        badge.style.zIndex = '2147483647';
        badge.style.boxShadow = '0 1px 3px rgba(0,0,0,0.5)';
        overlayContainer.appendChild(badge);

        items.push({
            id: currentId,
            tag: el.tagName.toLowerCase(),
            type: el.getAttribute('type') || '',
            role: el.getAttribute('role') || '',
            text: text,
            rect: {
                x: Math.round(rect.x + rect.width / 2),
                y: Math.round(rect.y + rect.height / 2),
                width: Math.round(rect.width),
                height: Math.round(rect.height),
                top: Math.round(rect.top),
                left: Math.round(rect.left)
            }
        });

        if (items.length >= 75) break; // Limit elements to prevent token overflow
    }

    return items;
})()
"""

DOM_CLEANUP_JS = """
(() => {
    const container = document.getElementById('__agent_overlay_container__');
    if (container) container.remove();
    document.querySelectorAll('[data-agent-id]').forEach(el => el.removeAttribute('data-agent-id'));
})()
"""

PAGE_CONTENT_JS = """
(() => {
    // Extract visible headings
    const headings = Array.from(document.querySelectorAll('h1, h2, h3'))
        .filter(h => h.offsetParent !== null)
        .map(h => `${h.tagName}: ${h.innerText.trim()}`)
        .slice(0, 8);

    // Extract main text content
    const paragraphs = Array.from(document.querySelectorAll('p, article, [role="main"]'))
        .filter(p => p.offsetParent !== null)
        .map(p => p.innerText.trim())
        .filter(t => t.length > 20)
        .slice(0, 5);

    return {
        headings: headings.join(' | '),
        content: paragraphs.join('\\n').substring(0, 1000)
    };
})()
"""

@dataclass
class DOMElement:
    id: int
    tag: str
    type: str
    role: str
    text: str
    rect: Dict[str, int]

    @property
    def center_x(self) -> int:
        return self.rect.get("x", 0)

    @property
    def center_y(self) -> int:
        return self.rect.get("y", 0)

class DOMAnnotator:
    """Manages Set-of-Marks DOM labeling and element state harvesting."""

    @staticmethod
    async def annotate_page(page) -> List[DOMElement]:
        """Injects labels and extracts visible interactive elements."""
        try:
            raw_elements = await page.evaluate(DOM_INJECT_JS)
            elements = []
            for item in raw_elements:
                elements.append(DOMElement(
                    id=item["id"],
                    tag=item["tag"],
                    type=item.get("type", ""),
                    role=item.get("role", ""),
                    text=item.get("text", ""),
                    rect=item.get("rect", {})
                ))
            return elements
        except Exception as e:
            print(f"[DOMAnnotator] Warning: Failed to annotate DOM: {e}")
            return []

    @staticmethod
    async def extract_page_summary(page) -> Dict[str, str]:
        """Extracts visible headings and main readable text paragraphs for text-only models."""
        try:
            return await page.evaluate(PAGE_CONTENT_JS)
        except Exception:
            return {"headings": "", "content": ""}

    @staticmethod
    async def cleanup_annotations(page) -> None:
        """Removes the badge overlay container from the DOM."""
        try:
            await page.evaluate(DOM_CLEANUP_JS)
        except Exception:
            pass

    @staticmethod
    def format_elements_for_prompt(elements: List[DOMElement]) -> str:
        """Produces a compact, high-signal text table of visible interactive elements."""
        if not elements:
            return "No interactive elements detected on the current screen."

        lines = ["ID | Tag | Type / Role | Text / Label"]
        lines.append("---|---|---|---")
        for el in elements:
            details = []
            if el.type:
                details.append(f"type={el.type}")
            if el.role:
                details.append(f"role={el.role}")
            meta = " ".join(details) if details else "-"
            clean_text = el.text.replace("|", "/")
            lines.append(f"[{el.id}] | <{el.tag}> | {meta} | {clean_text}")

        return "\n".join(lines)

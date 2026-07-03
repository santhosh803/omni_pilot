"""Browser service: Tavily-powered web search + optional Playwright page fetching.

The primary search backend is the Tavily Search API (already configured for the
research crew). Playwright is retained for fetching and rendering specific URLs
when full page content is needed (e.g. JS-rendered pages).
"""

import os

import httpx
from tavily import TavilyClient


def _tavily_configured() -> bool:
    key = os.getenv("TAVILY_API_KEY", "")
    return bool(key and key != "your_tavily_api_key_here")


async def search_web(query: str) -> str:
    """Searches the web via the Tavily Search API and returns formatted results.

    Falls back to a direct httpx-based DuckDuckGo Lite scrape only when Tavily
    is not configured, so the agent still works in degraded environments.
    """
    if _tavily_configured():
        return await _tavily_search(query)
    return await _fallback_search(query)


async def _tavily_search(query: str) -> str:
    """Uses the Tavily Search API to retrieve up to 5 results."""
    print(f"Browser Service: Searching via Tavily for '{query}'...")
    try:
        client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        # TavilyClient.search is synchronous — run in a thread to avoid blocking
        import asyncio

        response = await asyncio.to_thread(
            client.search, query=query, max_results=5, search_depth="advanced"
        )
        results = response.get("results", [])
        if not results:
            return "No search results returned from Tavily."

        formatted = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "Untitled")
            url = r.get("url", "")
            content = r.get("content", "")
            formatted.append(f"Result {i}: {title}\nURL: {url}\nSnippet: {content}")

        # Include the answer summary if Tavily provided one
        answer = response.get("answer")
        if answer:
            formatted.insert(0, f"Summary: {answer}")

        return "\n\n".join(formatted)
    except Exception as e:
        print(f"Browser Service (Tavily) Error: {e}")
        # Fall back to the legacy search if Tavily fails at runtime
        return await _fallback_search(query)


async def _fallback_search(query: str) -> str:
    """Lightweight fallback: scrapes DuckDuckGo Lite HTML via httpx (no browser needed)."""
    print(
        f"Browser Service: Tavily not configured — falling back to DuckDuckGo Lite for '{query}'..."
    )
    import urllib.parse

    encoded = urllib.parse.quote_plus(query)
    url = f"https://lite.duckduckgo.com/lite/?q={encoded}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        async with httpx.AsyncClient(
            timeout=10.0, headers=headers, follow_redirects=True
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text

        # Parse the simple HTML table from DDG Lite
        results = []
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            # DDG Lite uses simple <a> tags with class="result-link"
            links = soup.find_all("a", class_="result-link")
            for i, link in enumerate(links[:5], 1):
                title = link.get_text(strip=True)
                href = link.get("href", "")
                # The snippet is in the next <td> after the link's <td>
                parent_td = link.find_parent("td")
                snippet = ""
                if parent_td:
                    next_td = parent_td.find_next_sibling("td")
                    if next_td:
                        snippet = next_td.get_text(strip=True)
                results.append(f"Result {i}: {title}\nURL: {href}\nSnippet: {snippet}")
        except Exception:
            pass

        if not results:
            return "No search results returned from fallback search."

        return "\n\n".join(results)
    except Exception as e:
        print(f"Browser Service (fallback) Error: {e}")
        return f"Failed to execute web search: {str(e)}"


async def fetch_page(url: str) -> str:
    """Fetches and extracts plain text from a specific URL.

    Uses httpx for static pages and falls back to Playwright for JS-rendered
    pages that return minimal content.
    """
    print(f"Browser Service: Fetching page '{url}'...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # First attempt: httpx (fast, no browser)
    text = await _fetch_page_httpx(url, headers)
    if text and len(text) > 200:
        return text

    # Second attempt: Playwright (handles JS-rendered content)
    return await _fetch_page_playwright(url)


async def _fetch_page_httpx(url: str, headers: dict) -> str:
    """Fetches page content using httpx and extracts text with BeautifulSoup."""
    try:
        async with httpx.AsyncClient(
            timeout=10.0, headers=headers, follow_redirects=True
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n")
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            return "\n".join(chunk for chunk in chunks if chunk)
        except Exception:
            import re

            return re.sub(r"<[^>]+>", " ", html)
    except Exception as e:
        print(f"Browser Service (httpx fetch) Error: {e}")
        return ""


async def _fetch_page_playwright(url: str) -> str:
    """Fetches page content using Playwright for JS-rendered pages."""
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            content = await page.inner_text("body")
            await browser.close()
            return content
    except Exception as e:
        print(f"Browser Service (Playwright fetch) Error: {e}")
        return f"Failed to fetch page content: {str(e)}"

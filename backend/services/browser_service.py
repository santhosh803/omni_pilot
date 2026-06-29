import urllib.parse

from playwright.async_api import async_playwright


async def search_web(query: str) -> str:
    """Uses Playwright to search DuckDuckGo HTML and extract snippet results."""
    print(f"Browser Service: Searching DuckDuckGo for '{query}'...")

    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

    try:
        async with async_playwright() as p:
            # Launch headless browser
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            # Navigate to DDG HTML
            await page.goto(url, wait_until="domcontentloaded", timeout=10000)

            # Select search result components
            results = []
            snippets = await page.query_selector_all(".result__snippet")
            titles = await page.query_selector_all(".result__a")

            for i in range(min(3, len(snippets))):
                title_text = await titles[i].inner_text()
                snippet_text = await snippets[i].inner_text()
                results.append(f"Result {i + 1}: {title_text}\nSnippet: {snippet_text}")

            await browser.close()

            if not results:
                return "No search results returned from query."

            return "\n\n".join(results)

    except Exception as e:
        print(f"Browser Service Error: {e}")
        return f"Failed to execute web search: {str(e)}"

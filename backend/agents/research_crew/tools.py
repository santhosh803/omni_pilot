import os
import httpx
import re
from crewai.tools import tool
from tavily import TavilyClient

@tool("TavilySearch")
def tavily_search(query: str) -> list:
    """Search the web for the given query using Tavily and return a list of results."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key or api_key == "your_tavily_api_key_here":
        return [{"title": "Error", "url": "", "content": "TAVILY_API_KEY is not configured or is a placeholder."}]
    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(query=query)
        results = response.get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", "")
            }
            for r in results
        ]
    except Exception as e:
        return [{"title": "Error", "url": "", "content": f"Search failed: {str(e)}"}]

@tool("fetch_page_content")
def fetch_page_content(url: str) -> str:
    """Fetch the HTML content from the given URL and return the plain text content."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
            html = response.text
            
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                # Remove non-content elements
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()
                text = soup.get_text(separator="\n")
                # Clean up whitespace
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = "\n".join(chunk for chunk in chunks if chunk)
                return text
            except Exception:
                # Basic tags stripping fallback
                text = re.sub(r'<[^>]+>', ' ', html)
                return " ".join(text.split())
    except Exception as e:
        print(f"Error fetching page content for {url}: {e}")
        return ""

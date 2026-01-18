"""LLM API for AWS Bedrock Web Search."""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiohttp
import voluptuous as vol

from homeassistant.helpers import llm
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.json import JsonObjectType

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


class WebSearchTool(llm.Tool):
    """Tool for web search and URL fetching."""

    name = "search"
    description = (
        "Search the web for current information or fetch content from specific URLs. "
        "Use this tool when you need: "
        "1. Recent events, news, or current data (e.g., 'What's happening today?', 'Current weather forecast'). "
        "2. Information that changes frequently (e.g., stock prices, sports scores, election results). "
        "3. Content from specific websites or URLs. "
        "4. Facts or data beyond your training cutoff date. "
        "Use action='search' with a query to search Google, or action='fetch' with a url to retrieve specific webpage content."
    )

    parameters = vol.Schema(
        {
            vol.Required(
                "action",
                description="Action to perform: 'search' to search Google with a query, 'fetch' to retrieve content from a specific URL",
            ): vol.In(["search", "fetch"]),
            vol.Optional(
                "query",
                description="Search query for Google search (required when action is 'search'). Be specific and use relevant keywords.",
            ): str,
            vol.Optional(
                "url",
                description="The complete URL to fetch content from (required when action is 'fetch'). Must include protocol (http:// or https://).",
            ): str,
        }
    )

    def __init__(
        self, hass: HomeAssistant, google_api_key: str, google_cse_id: str
    ) -> None:
        """Initialize the web search tool."""
        self.hass = hass
        self.google_api_key = google_api_key
        self.google_cse_id = google_cse_id

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Execute the web search tool."""
        action = tool_input.tool_args.get("action", "fetch")
        query = tool_input.tool_args.get("query", "")
        url = tool_input.tool_args.get("url", "")

        if action == "search":
            if not query:
                return {"error": "No search query provided"}

            if self.google_api_key and self.google_cse_id:
                return await self._async_google_search(query)

            return {"error": "Google Search API not configured"}

        if action == "fetch":
            if not url:
                return {"error": "No URL provided"}

            return await self._async_fetch_url(url)

        return {"error": f"Unknown action: {action}"}

    async def _async_google_search(self, query: str) -> JsonObjectType:
        """Perform Google Custom Search API query."""
        try:
            session = async_get_clientsession(self.hass)
            timeout = aiohttp.ClientTimeout(total=10)

            # Google Custom Search API endpoint
            api_url = "https://www.googleapis.com/customsearch/v1"
            params: dict[str, str | int] = {
                "key": self.google_api_key,
                "cx": self.google_cse_id,
                "q": query,
                "num": 5,
            }

            LOGGER.debug("Making Google Search API request for query: %s", query)

            async with session.get(api_url, params=params, timeout=timeout) as response:
                if response.status != 200:
                    error_text = await response.text()
                    LOGGER.error(
                        "Google Search API error (status %d): %s",
                        response.status,
                        error_text,
                    )
                    return {
                        "error": f"Google Search API returned status {response.status}"
                    }

                data = await response.json()

                # Extract search results
                items = data.get("items", [])
                if not items:
                    return {"result": "No search results found"}

                # Format results
                results = []
                for item in items:
                    title = item.get("title", "")
                    link = item.get("link", "")
                    snippet = item.get("snippet", "")
                    results.append(f"**{title}**\n{link}\n{snippet}")

                formatted_results = "\n\n".join(results)
                return {
                    "result": f"Search results for '{query}':\n\n{formatted_results}"
                }

        except aiohttp.ClientError as err:
            LOGGER.error("HTTP error during Google search: %s", err)
            return {"error": f"HTTP error during search: {err}"}
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("Unexpected error during Google search")
            return {"error": f"Error during search: {err}"}

    async def _async_fetch_url(self, url: str) -> JsonObjectType:
        """Fetch content from a URL."""
        try:
            session = async_get_clientsession(self.hass)
            timeout = aiohttp.ClientTimeout(total=10)

            async with session.get(url, timeout=timeout) as response:
                if response.status != 200:
                    return {"error": f"HTTP {response.status} when fetching {url}"}

                text = await response.text()
                # Limit content size to prevent token overload
                if len(text) > 5000:
                    text = text[:5000] + "... (content truncated)"

                return {"result": text}

        except aiohttp.ClientError as err:
            LOGGER.error("HTTP error fetching URL %s: %s", url, err)
            return {"error": f"HTTP error fetching URL: {err}"}
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("Error fetching URL %s", url)
            return {"error": f"Error fetching URL: {err}"}


class AWSBedrockWebSearchAPI(llm.API):
    """AWS Bedrock Web Search API for LLMs."""

    def __init__(
        self, hass: HomeAssistant, google_api_key: str, google_cse_id: str
    ) -> None:
        """Initialize the API."""
        super().__init__(
            hass=hass,
            id=f"{DOMAIN}_web_search",
            name="AWS Bedrock Web Search",
        )
        self.google_api_key = google_api_key
        self.google_cse_id = google_cse_id

    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return the instance of the API."""
        return llm.APIInstance(
            api=self,
            api_prompt=(
                "You have access to web search via the web_search tool. "
                "IMPORTANT: Use this tool whenever questions require:\n"
                "- Current events, news, or real-time information\n"
                "- Data that changes frequently (weather, stocks, scores)\n"
                "- Facts published after your training date\n"
                "- Content from specific websites or URLs\n\n"
                "Do NOT guess or use outdated information when current data is needed. "
                "Always use web_search for questions about 'today', 'now', 'current', 'latest', or specific recent dates."
            ),
            llm_context=llm_context,
            tools=[WebSearchTool(self.hass, self.google_api_key, self.google_cse_id)],
        )

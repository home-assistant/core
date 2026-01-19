"""LLM API for AWS Bedrock Web Search."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import aiohttp
import trafilatura
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
        "Use this tool when the user asks for information not available in your training data or Home Assistant."
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
            return await self._async_google_search(query)

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

                # Format results in a structured way for LLM to analyze and fetch
                results = []
                for idx, item in enumerate(items, 1):
                    title = item.get("title", "")
                    link = item.get("link", "")
                    snippet = item.get("snippet", "")
                    results.append(
                        f"[{idx}] {title}\n    URL: {link}\n    Summary: {snippet}"
                    )

                formatted_results = "\n\n".join(results)
                return {
                    "result": (
                        f"Search results for '{query}':\n\n"
                        f"{formatted_results}\n\n"
                        "---\n"
                        "To get detailed information, use 'fetch' action with the "
                        "URL of the most relevant result above."
                    )
                }

        except aiohttp.ClientError as err:
            LOGGER.error("HTTP error during Google search: %s", err)
            return {"error": f"HTTP error during search: {err}"}
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("Unexpected error during Google search")
            return {"error": f"Error during search: {err}"}

    async def _async_fetch_url(self, url: str) -> JsonObjectType:
        """Fetch content from a URL and convert to LLM-friendly markdown."""
        try:
            session = async_get_clientsession(self.hass)
            timeout = aiohttp.ClientTimeout(total=15)

            async with session.get(url, timeout=timeout) as response:
                if response.status != 200:
                    return {"error": f"HTTP {response.status} when fetching {url}"}

                html_content = await response.text()

                # Use trafilatura to extract clean, LLM-friendly content
                # Run in executor since trafilatura uses blocking I/O
                extracted_text = await self.hass.async_add_executor_job(
                    partial(
                        trafilatura.extract,
                        html_content,
                        output_format="markdown",
                        include_tables=True,
                        include_links=True,
                        include_formatting=True,
                        include_comments=False,
                        favor_precision=True,
                        url=url,
                    )
                )

                if not extracted_text:
                    # Fallback to baseline extraction if main extraction fails
                    _, extracted_text, _ = await self.hass.async_add_executor_job(
                        trafilatura.baseline, html_content
                    )

                if not extracted_text:
                    return {"error": "Could not extract meaningful content from page"}

                # Limit content size to prevent token overload
                max_length = 8000
                if len(extracted_text) > max_length:
                    extracted_text = (
                        extracted_text[:max_length] + "\n\n... (content truncated)"
                    )

                return {"result": extracted_text}

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
                "You have access to web search via the 'search' tool. "
                "Use this tool when the user asks for information not available "
                "in your training data or Home Assistant.\n\n"
                "IMPORTANT: Follow this chain-of-thought process:\n"
                "1. SEARCH: Use action='search' with a specific query to find relevant sources\n"
                "2. ANALYZE: Review the search results and identify the most relevant URL\n"
                "3. FETCH: Use action='fetch' with the chosen URL to retrieve detailed content\n"
                "4. ANSWER: Synthesize the fetched information to answer the user's question\n\n"
                "Do NOT guess or use outdated information when current data is needed. "
                "Always complete the full search → fetch cycle before answering."
            ),
            llm_context=llm_context,
            tools=[WebSearchTool(self.hass, self.google_api_key, self.google_cse_id)],
        )

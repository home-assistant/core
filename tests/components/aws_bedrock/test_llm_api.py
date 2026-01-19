"""Tests for the AWS Bedrock LLM API."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import aiohttp
import pytest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from tests.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.aws_bedrock.llm_api import (
    AWSBedrockWebSearchAPI,
    WebSearchTool,
)
from homeassistant.helpers import llm


@pytest.fixture
def mock_session():
    """Mock aiohttp session."""
    return MagicMock()


@pytest.fixture
def web_search_tool(hass: HomeAssistant) -> WebSearchTool:
    """Create a WebSearchTool instance."""
    return WebSearchTool(hass, "test_api_key", "test_cse_id")


@pytest.fixture
def llm_context() -> llm.LLMContext:
    """Create an LLM context."""
    return llm.LLMContext(
        platform="test_platform",
        context=None,
        language="en",
        assistant="conversation",
        device_id=None,
    )


async def test_web_search_tool_initialization(
    hass: HomeAssistant, web_search_tool: WebSearchTool
) -> None:
    """Test WebSearchTool initialization."""
    assert web_search_tool.name == "search"
    assert web_search_tool.hass == hass
    assert web_search_tool.google_api_key == "test_api_key"
    assert web_search_tool.google_cse_id == "test_cse_id"
    assert web_search_tool.description is not None
    assert "Search the web" in web_search_tool.description


async def test_async_call_search_action(
    hass: HomeAssistant, web_search_tool: WebSearchTool, llm_context: llm.LLMContext
) -> None:
    """Test async_call with search action."""
    tool_input = llm.ToolInput(
        tool_name="search",
        tool_args={"action": "search", "query": "test query"},
    )

    with patch.object(
        web_search_tool, "_async_google_search", return_value={"result": "test results"}
    ) as mock_search:
        result = await web_search_tool.async_call(hass, tool_input, llm_context)
        assert result == {"result": "test results"}
        mock_search.assert_called_once_with("test query")


async def test_async_call_search_action_no_query(
    hass: HomeAssistant, web_search_tool: WebSearchTool, llm_context: llm.LLMContext
) -> None:
    """Test async_call with search action but no query."""
    tool_input = llm.ToolInput(
        tool_name="search",
        tool_args={"action": "search"},
    )

    result = await web_search_tool.async_call(hass, tool_input, llm_context)
    assert result == {"error": "No search query provided"}


async def test_async_call_fetch_action(
    hass: HomeAssistant, web_search_tool: WebSearchTool, llm_context: llm.LLMContext
) -> None:
    """Test async_call with fetch action."""
    tool_input = llm.ToolInput(
        tool_name="search",
        tool_args={"action": "fetch", "url": "https://example.com"},
    )

    with patch.object(
        web_search_tool, "_async_fetch_url", return_value={"result": "page content"}
    ) as mock_fetch:
        result = await web_search_tool.async_call(hass, tool_input, llm_context)
        assert result == {"result": "page content"}
        mock_fetch.assert_called_once_with("https://example.com")


async def test_async_call_fetch_action_no_url(
    hass: HomeAssistant, web_search_tool: WebSearchTool, llm_context: llm.LLMContext
) -> None:
    """Test async_call with fetch action but no URL."""
    tool_input = llm.ToolInput(
        tool_name="search",
        tool_args={"action": "fetch"},
    )

    result = await web_search_tool.async_call(hass, tool_input, llm_context)
    assert result == {"error": "No URL provided"}


async def test_async_call_unknown_action(
    hass: HomeAssistant, web_search_tool: WebSearchTool, llm_context: llm.LLMContext
) -> None:
    """Test async_call with unknown action."""
    tool_input = llm.ToolInput(
        tool_name="search",
        tool_args={"action": "unknown"},
    )

    result = await web_search_tool.async_call(hass, tool_input, llm_context)
    assert result == {"error": "Unknown action: unknown"}


async def test_async_google_search_success(
    web_search_tool: WebSearchTool,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test successful Google search."""
    aioclient_mock.get(
        "https://www.googleapis.com/customsearch/v1",
        json={
            "items": [
                {
                    "title": "Result 1",
                    "link": "https://example.com/1",
                    "snippet": "First result",
                },
                {
                    "title": "Result 2",
                    "link": "https://example.com/2",
                    "snippet": "Second result",
                },
            ]
        },
    )

    result = await web_search_tool._async_google_search("test query")

    assert "result" in result
    assert isinstance(result["result"], str)
    assert "Search results for 'test query'" in result["result"]
    assert "[1] Result 1" in result["result"]
    assert "https://example.com/1" in result["result"]
    assert "[2] Result 2" in result["result"]
    assert "https://example.com/2" in result["result"]
    assert "To get detailed information" in result["result"]


async def test_async_google_search_no_results(
    web_search_tool: WebSearchTool,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test Google search with no results."""
    aioclient_mock.get(
        "https://www.googleapis.com/customsearch/v1",
        json={"items": []},
    )

    result = await web_search_tool._async_google_search("nonexistent query")

    assert result == {"result": "No search results found"}


async def test_async_google_search_api_error(
    web_search_tool: WebSearchTool,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test Google search with API error response."""
    aioclient_mock.get(
        "https://www.googleapis.com/customsearch/v1",
        status=403,
        text="API key invalid",
    )

    result = await web_search_tool._async_google_search("test query")

    assert result == {"error": "Google Search API returned status 403"}


async def test_async_google_search_client_error(
    web_search_tool: WebSearchTool,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test Google search with client error."""
    aioclient_mock.get(
        "https://www.googleapis.com/customsearch/v1",
        exc=aiohttp.ClientError("Connection failed"),
    )

    result = await web_search_tool._async_google_search("test query")

    assert "error" in result
    assert isinstance(result["error"], str)
    assert "HTTP error during search" in result["error"]


async def test_async_google_search_unexpected_error(
    web_search_tool: WebSearchTool,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test Google search with unexpected error."""
    aioclient_mock.get(
        "https://www.googleapis.com/customsearch/v1",
        exc=ValueError("Unexpected error"),
    )

    result = await web_search_tool._async_google_search("test query")

    assert "error" in result
    assert isinstance(result["error"], str)
    assert "Error during search" in result["error"]


async def test_async_fetch_url_success(
    hass: HomeAssistant,
    web_search_tool: WebSearchTool,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test successful URL fetch."""
    aioclient_mock.get(
        "https://example.com",
        text="<html><body>Test content</body></html>",
    )

    async def mock_extract_async(*args, **kwargs):
        """Mock trafilatura extract."""
        return "# Test Content\n\nExtracted markdown content"

    with patch.object(
        hass,
        "async_add_executor_job",
        side_effect=lambda func, *args: mock_extract_async(),
    ):
        result = await web_search_tool._async_fetch_url("https://example.com")

    assert "result" in result
    assert isinstance(result["result"], str)
    assert "# Test Content" in result["result"]
    assert "Extracted markdown content" in result["result"]


async def test_async_fetch_url_http_error(
    web_search_tool: WebSearchTool,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test URL fetch with HTTP error."""
    aioclient_mock.get(
        "https://example.com",
        status=404,
    )

    result = await web_search_tool._async_fetch_url("https://example.com")

    assert result == {"error": "HTTP 404 when fetching https://example.com"}


async def test_async_fetch_url_no_content_extracted(
    hass: HomeAssistant,
    web_search_tool: WebSearchTool,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test URL fetch when no content can be extracted."""
    aioclient_mock.get(
        "https://example.com",
        text="<html><body>Empty</body></html>",
    )

    def mock_extract_none(*args, **kwargs):
        """Mock trafilatura extract returning None."""

    def mock_baseline(*args, **kwargs):
        """Mock trafilatura baseline returning empty."""
        return None, None, None

    # Track which executor job is being called
    call_count = [0]

    async def async_add_executor_job_side_effect(func, *args):
        """Side effect for async_add_executor_job."""
        call_count[0] += 1
        if call_count[0] == 1:
            # First call is extract - return None
            return mock_extract_none()
        # Second call is baseline - return None
        return mock_baseline()

    with patch.object(
        hass,
        "async_add_executor_job",
        side_effect=async_add_executor_job_side_effect,
    ):
        result = await web_search_tool._async_fetch_url("https://example.com")

    assert result == {"error": "Could not extract meaningful content from page"}


async def test_async_fetch_url_content_truncation(
    hass: HomeAssistant,
    web_search_tool: WebSearchTool,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test URL fetch with content truncation."""
    aioclient_mock.get(
        "https://example.com",
        text="<html><body>Test</body></html>",
    )

    # Create very long content that will be truncated
    long_content = "A" * 9000

    async def mock_extract_async(*args, **kwargs):
        """Mock trafilatura extract with long content."""
        return long_content

    with patch.object(
        hass,
        "async_add_executor_job",
        side_effect=lambda func, *args: mock_extract_async(),
    ):
        result = await web_search_tool._async_fetch_url("https://example.com")

    assert "result" in result
    assert isinstance(result["result"], str)
    assert len(result["result"]) < len(long_content)
    assert "(content truncated)" in result["result"]


async def test_async_fetch_url_client_error(
    web_search_tool: WebSearchTool,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test URL fetch with client error."""
    aioclient_mock.get(
        "https://example.com",
        exc=aiohttp.ClientError("Connection failed"),
    )

    result = await web_search_tool._async_fetch_url("https://example.com")

    assert "error" in result
    assert isinstance(result["error"], str)
    assert "HTTP error fetching URL" in result["error"]


async def test_async_fetch_url_unexpected_error(
    web_search_tool: WebSearchTool,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test URL fetch with unexpected error."""
    aioclient_mock.get(
        "https://example.com",
        exc=ValueError("Unexpected error"),
    )

    result = await web_search_tool._async_fetch_url("https://example.com")

    assert "error" in result
    assert isinstance(result["error"], str)
    assert "Error fetching URL" in result["error"]


async def test_aws_bedrock_web_search_api_initialization(
    hass: HomeAssistant,
) -> None:
    """Test AWSBedrockWebSearchAPI initialization."""
    api = AWSBedrockWebSearchAPI(hass, "test_api_key", "test_cse_id")

    assert api.hass == hass
    assert api.google_api_key == "test_api_key"
    assert api.google_cse_id == "test_cse_id"
    assert api.id == "aws_bedrock_web_search"
    assert api.name == "AWS Bedrock Web Search"


async def test_async_get_api_instance(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test async_get_api_instance."""
    api = AWSBedrockWebSearchAPI(hass, "test_api_key", "test_cse_id")
    instance = await api.async_get_api_instance(llm_context)

    assert isinstance(instance, llm.APIInstance)
    assert instance.api == api
    assert instance.llm_context == llm_context
    assert "web search via the 'search' tool" in instance.api_prompt
    assert "chain-of-thought" in instance.api_prompt
    assert len(instance.tools) == 1
    assert isinstance(instance.tools[0], WebSearchTool)
    assert instance.tools[0].google_api_key == "test_api_key"
    assert instance.tools[0].google_cse_id == "test_cse_id"

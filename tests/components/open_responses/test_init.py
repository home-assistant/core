"""Tests for the Open Responses integration."""

from unittest.mock import AsyncMock, Mock, patch

from homeassistant.components.open_responses.const import CONF_BASE_URL, DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_setup_entry_passes_base_url(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup passes the configured base URL to the OpenAI SDK."""
    mock_client = Mock()
    mock_client.platform_headers = Mock(return_value={})
    mock_client.models.list = AsyncMock()

    with patch(
        "homeassistant.components.open_responses.openai.AsyncOpenAI",
        return_value=mock_client,
    ) as mock_async_openai:
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    mock_async_openai.assert_called_once()
    assert mock_async_openai.call_args.kwargs[CONF_API_KEY] == "bla"
    assert (
        mock_async_openai.call_args.kwargs[CONF_BASE_URL] == "https://example.local/v1"
    )
    assert mock_config_entry.runtime_data is mock_client

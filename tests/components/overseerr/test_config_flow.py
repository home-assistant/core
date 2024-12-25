"""Tests for the Overseerr config flow."""

from unittest.mock import AsyncMock

from python_overseerr.exceptions import OverseerrConnectionError

from homeassistant.components.overseerr.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://overseerr.test", CONF_API_KEY: "test-key"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Overseerr"
    assert result["data"] == {
        CONF_URL: "http://overseerr.test",
        CONF_API_KEY: "test-key",
    }


async def test_flow_errors(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test flow errors."""
    mock_overseerr_client.get_request_count.side_effect = OverseerrConnectionError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://overseerr.test", CONF_API_KEY: "test-key"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_overseerr_client.get_request_count.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://overseerr.test", CONF_API_KEY: "test-key"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://overseerr.test", CONF_API_KEY: "test-key"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

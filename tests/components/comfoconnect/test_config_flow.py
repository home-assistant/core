"""Tests for the Comfoconnect config flow."""

from unittest.mock import AsyncMock

from homeassistant.components.comfoconnect import (
    CONF_USER_AGENT,
    DEFAULT_PIN,
    DEFAULT_TOKEN,
    DEFAULT_USER_AGENT,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PIN, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant,
    mock_comfoconnect_bridge: AsyncMock,
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
        {
            CONF_HOST: "10.0.0.131",
            CONF_TOKEN: DEFAULT_TOKEN,
            CONF_PIN: DEFAULT_PIN,
            CONF_USER_AGENT: DEFAULT_USER_AGENT,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Comfoconnect"
    assert result["data"] == {
        CONF_HOST: "10.0.0.131",
        CONF_TOKEN: DEFAULT_TOKEN,
        CONF_PIN: DEFAULT_PIN,
        CONF_USER_AGENT: DEFAULT_USER_AGENT,
    }
    assert result["result"].unique_id == "3030"


async def test_token_length(
    hass: HomeAssistant,
    mock_comfoconnect_bridge: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test error when token is not 32 characters."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "10.0.0.131",
            CONF_TOKEN: "0",
            CONF_PIN: DEFAULT_PIN,
            CONF_USER_AGENT: DEFAULT_USER_AGENT,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_TOKEN: "invalid_token"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "10.0.0.131",
            CONF_TOKEN: DEFAULT_TOKEN,
            CONF_PIN: DEFAULT_PIN,
            CONF_USER_AGENT: DEFAULT_USER_AGENT,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_no_bridge(
    hass: HomeAssistant,
    mock_comfoconnect_bridge: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test error when no bridge found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_comfoconnect_bridge.discover.return_value = []

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "10.0.0.131",
            CONF_TOKEN: DEFAULT_TOKEN,
            CONF_PIN: DEFAULT_PIN,
            CONF_USER_AGENT: DEFAULT_USER_AGENT,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_bridge = AsyncMock()
    mock_bridge.uuid = b"00"

    mock_comfoconnect_bridge.discover.return_value = [mock_bridge]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "10.0.0.131",
            CONF_TOKEN: DEFAULT_TOKEN,
            CONF_PIN: DEFAULT_PIN,
            CONF_USER_AGENT: DEFAULT_USER_AGENT,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_comfoconnect_bridge: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error when duplicate entry."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "10.0.0.131",
            CONF_TOKEN: DEFAULT_TOKEN,
            CONF_PIN: DEFAULT_PIN,
            CONF_USER_AGENT: DEFAULT_USER_AGENT,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow(
    hass: HomeAssistant,
    mock_comfoconnect_bridge: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test full import flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "10.0.0.131",
            CONF_TOKEN: DEFAULT_TOKEN,
            CONF_PIN: DEFAULT_PIN,
            CONF_USER_AGENT: DEFAULT_USER_AGENT,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Comfoconnect"
    assert result["data"] == {
        CONF_HOST: "10.0.0.131",
        CONF_TOKEN: DEFAULT_TOKEN,
        CONF_PIN: DEFAULT_PIN,
        CONF_USER_AGENT: DEFAULT_USER_AGENT,
    }
    assert result["result"].unique_id == "3030"


async def test_import_no_bridge(
    hass: HomeAssistant,
    mock_comfoconnect_bridge: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test error when no bridge found."""
    mock_comfoconnect_bridge.discover.return_value = []
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "10.0.0.131",
            CONF_TOKEN: DEFAULT_TOKEN,
            CONF_PIN: DEFAULT_PIN,
            CONF_USER_AGENT: DEFAULT_USER_AGENT,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"

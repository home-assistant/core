"""Test the BirdNET-Go config flow."""

from unittest.mock import AsyncMock

from aiobirdnetgo import (
    BirdNetGoAuthenticationError,
    BirdNetGoConnectionError,
    BirdNetGoError,
)

from homeassistant.components.birdnet_go.const import DEFAULT_PORT, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_flow_user_success(
    hass: HomeAssistant, mock_birdnet_client: AsyncMock
) -> None:
    """Test successful user step configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "BirdNET-Go (192.168.1.100:8080)"
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: DEFAULT_PORT,
        CONF_SSL: False,
    }
    assert result["result"].unique_id == "192.168.1.100:8080"


async def test_flow_user_cannot_connect(
    hass: HomeAssistant, mock_birdnet_client: AsyncMock
) -> None:
    """Test user step with connection error."""
    mock_birdnet_client.get_health.side_effect = BirdNetGoConnectionError(
        "Host unreachable"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover from error
    mock_birdnet_client.get_health.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_user_invalid_auth(
    hass: HomeAssistant, mock_birdnet_client: AsyncMock
) -> None:
    """Test user step with authentication error."""
    mock_birdnet_client.get_health.side_effect = BirdNetGoAuthenticationError(
        "Bad credentials"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_flow_user_general_error(
    hass: HomeAssistant, mock_birdnet_client: AsyncMock
) -> None:
    """Test user step with general BirdNET-Go error."""
    mock_birdnet_client.get_health.side_effect = BirdNetGoError("General failure")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_user_unknown_exception(
    hass: HomeAssistant, mock_birdnet_client: AsyncMock
) -> None:
    """Test user step with unexpected exception."""
    mock_birdnet_client.get_health.side_effect = RuntimeError("Fatal memory error")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_flow_user_already_configured(
    hass: HomeAssistant,
    mock_birdnet_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test aborting when unique ID is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

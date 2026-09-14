"""Test the Envertech EVT800 config flow."""

from unittest.mock import AsyncMock

from homeassistant.components.envertech_evt800.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_USER_INPUT

from tests.conftest import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_evt800_client: AsyncMock
) -> None:
    """Test completing a full flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: MOCK_USER_INPUT[CONF_IP_ADDRESS],
            CONF_PORT: MOCK_USER_INPUT[CONF_PORT],
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Envertech EVT800"
    assert result["data"] == MOCK_USER_INPUT

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_errors(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_evt800_client: AsyncMock
) -> None:
    """Test encountering errors when configuring the integration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_evt800_client.test_connection.return_value = False
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_IP_ADDRESS: MOCK_USER_INPUT[CONF_IP_ADDRESS],
            CONF_PORT: MOCK_USER_INPUT[CONF_PORT],
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    mock_evt800_client.test_connection.return_value = True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: MOCK_USER_INPUT[CONF_IP_ADDRESS],
            CONF_PORT: MOCK_USER_INPUT[CONF_PORT],
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_evt800_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test starting a flow by user when already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_IP_ADDRESS: MOCK_USER_INPUT[CONF_IP_ADDRESS],
            CONF_PORT: MOCK_USER_INPUT[CONF_PORT],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

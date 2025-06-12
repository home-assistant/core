"""Tests for Comelit SimpleHome switch platform."""

from unittest.mock import AsyncMock

from aiocomelit.exceptions import CannotAuthenticate, CannotConnect, CannotRetrieveData
import pytest

from homeassistant.components.comelit.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SERVICE_TURN_ON
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration

from tests.common import MockConfigEntry

ENTITY_ID = "switch.switch0"


@pytest.mark.parametrize(
    ("side_effect", "key", "error"),
    [
        (CannotConnect, "cannot_connect", "CannotConnect()"),
        (CannotRetrieveData, "cannot_retrieve_data", "CannotRetrieveData()"),
    ],
)
async def test_bridge_api_call_exceptions(
    hass: HomeAssistant,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
    side_effect: Exception,
    key: str,
    error: str,
) -> None:
    """Test bridge_api_call decorator for exceptions."""

    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_OFF

    mock_serial_bridge.set_device_status.side_effect = side_effect

    # Call API
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == key
    assert exc_info.value.translation_placeholders == {"error": error}


async def test_bridge_api_call_reauth(
    hass: HomeAssistant,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test bridge_api_call decorator for reauth."""

    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_OFF

    mock_serial_bridge.set_device_status.side_effect = CannotAuthenticate

    # Call API
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert mock_serial_bridge_config_entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_serial_bridge_config_entry.entry_id

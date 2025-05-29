"""Tests for Comelit SimpleHome utils."""

from unittest.mock import AsyncMock

from aiocomelit.api import ComelitSerialBridgeObject
from aiocomelit.const import CLIMATE, WATT
from aiocomelit.exceptions import CannotAuthenticate, CannotConnect, CannotRetrieveData
import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.components.comelit.const import DOMAIN
from homeassistant.components.humidifier import ATTR_HUMIDITY
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SERVICE_TURN_ON
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration

from tests.common import MockConfigEntry

ENTITY_ID_0 = "switch.switch0"
ENTITY_ID_1 = "climate.climate0"
ENTITY_ID_2 = "humidifier.climate0_dehumidifier"
ENTITY_ID_3 = "humidifier.climate0_humidifier"


async def test_device_remove_stale(
    hass: HomeAssistant,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test removal of stale devices with no entities."""

    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert (state := hass.states.get(ENTITY_ID_1))
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 5.0

    assert (state := hass.states.get(ENTITY_ID_2))
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_HUMIDITY] == 50.0

    assert (state := hass.states.get(ENTITY_ID_3))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_HUMIDITY] == 50.0

    mock_serial_bridge.get_all_devices.return_value[CLIMATE] = {
        0: ComelitSerialBridgeObject(
            index=0,
            name="Climate0",
            status=0,
            human_status="off",
            type="climate",
            val=[
                [0, 0, "O", "A", 0, 0, 0, "N"],
                [0, 0, "O", "A", 0, 0, 0, "N"],
                [0, 0],
            ],
            protected=0,
            zone="Living room",
            power=0.0,
            power_unit=WATT,
        ),
    }

    await hass.config_entries.async_reload(mock_serial_bridge_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID_1)) is None
    assert (state := hass.states.get(ENTITY_ID_2)) is None
    assert (state := hass.states.get(ENTITY_ID_3)) is None


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

    assert (state := hass.states.get(ENTITY_ID_0))
    assert state.state == STATE_OFF

    mock_serial_bridge.set_device_status.side_effect = side_effect

    # Call API
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID_0},
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

    assert (state := hass.states.get(ENTITY_ID_0))
    assert state.state == STATE_OFF

    mock_serial_bridge.set_device_status.side_effect = CannotAuthenticate

    # Call API
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID_0},
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

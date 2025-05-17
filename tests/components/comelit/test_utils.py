"""Tests for Comelit SimpleHome utils."""

from unittest.mock import AsyncMock

from aiocomelit.api import ComelitSerialBridgeObject
from aiocomelit.const import CLIMATE, WATT

from homeassistant.components.climate import HVACMode
from homeassistant.components.humidifier import ATTR_HUMIDITY
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry

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

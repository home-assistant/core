"""Tests of the climate entity of the balboa integration."""
from unittest.mock import MagicMock

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import init_integration

ENTITY_BINARY_SENSOR = "binary_sensor.fakespa_"

FILTER_MAP = [
    [STATE_OFF, STATE_OFF],
    [STATE_ON, STATE_OFF],
    [STATE_OFF, STATE_ON],
    [STATE_ON, STATE_ON],
]


async def test_filters(hass: HomeAssistant, client: MagicMock) -> None:
    """Test spa filters."""

    config_entry = await init_integration(hass)

    for filter_mode in range(4):
        for spa_filter in range(1, 3):
            state = await _patch_filter(
                hass, config_entry, filter_mode, spa_filter, client
            )
            assert state.state == FILTER_MAP[filter_mode][spa_filter - 1]


async def test_circ_pump(hass: HomeAssistant, client: MagicMock) -> None:
    """Test spa circ pump."""
    client.have_circ_pump.return_value = (True,)
    config_entry = await init_integration(hass)

    state = await _patch_circ_pump(hass, config_entry, True, client)
    assert state.state == STATE_ON
    state = await _patch_circ_pump(hass, config_entry, False, client)
    assert state.state == STATE_OFF


async def _patch_circ_pump(hass, config_entry, pump_state, client):
    """Patch the circ pump state."""
    client.get_circ_pump.return_value = pump_state
    await client.new_data_cb()
    await hass.async_block_till_done()
    return hass.states.get(f"{ENTITY_BINARY_SENSOR}circ_pump")


async def _patch_filter(hass, config_entry, filter_mode, num, client):
    """Patch the filter state."""
    client.get_filtermode.return_value = filter_mode
    await client.new_data_cb()
    await hass.async_block_till_done()
    return hass.states.get(f"{ENTITY_BINARY_SENSOR}filter{num}")

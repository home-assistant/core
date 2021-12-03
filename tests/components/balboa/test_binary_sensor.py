"""Tests of the climate entity of the balboa integration."""

from unittest.mock import patch

from homeassistant.components.balboa.const import DOMAIN as BALBOA_DOMAIN, SIGNAL_UPDATE
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component

from . import init_integration_mocked

ENTITY_BINARY_SENSOR = "binary_sensor.fakespa_"

FILTER_MAP = [
    [STATE_OFF, STATE_OFF],
    [STATE_ON, STATE_OFF],
    [STATE_OFF, STATE_ON],
    [STATE_ON, STATE_ON],
]


async def test_filters(hass: HomeAssistant):
    """Test spa filters."""

    config_entry = await _setup_binary_sensor_test(hass)

    for filter_mode in range(4):
        for spa_filter in range(1, 3):
            state = await _patch_filter(hass, config_entry, filter_mode, spa_filter)
            assert state.state == FILTER_MAP[filter_mode][spa_filter - 1]


async def test_circ_pump(hass: HomeAssistant):
    """Test spa circ pump."""
    with patch(
        "homeassistant.components.balboa.BalboaSpaWifi.have_circ_pump",
        return_value=True,
    ):
        config_entry = await _setup_binary_sensor_test(hass)

    state = await _patch_circ_pump(hass, config_entry, True)
    assert state.state == STATE_ON
    state = await _patch_circ_pump(hass, config_entry, False)
    assert state.state == STATE_OFF


async def _patch_circ_pump(hass, config_entry, pump_state):
    """Patch the circ pump state."""
    with patch(
        "homeassistant.components.balboa.BalboaSpaWifi.get_circ_pump",
        return_value=pump_state,
    ):
        async_dispatcher_send(hass, SIGNAL_UPDATE.format(config_entry.entry_id))
        await hass.async_block_till_done()
        return hass.states.get(f"{ENTITY_BINARY_SENSOR}circ_pump")


async def _patch_filter(hass, config_entry, filter_mode, num):
    """Patch the filter state."""
    with patch(
        "homeassistant.components.balboa.BalboaSpaWifi.get_filtermode",
        return_value=filter_mode,
    ):
        async_dispatcher_send(hass, SIGNAL_UPDATE.format(config_entry.entry_id))
        await hass.async_block_till_done()
        return hass.states.get(f"{ENTITY_BINARY_SENSOR}filter{num}")


async def _setup_binary_sensor_test(hass):
    """Prepare the test."""
    config_entry = await init_integration_mocked(hass)
    await async_setup_component(hass, BALBOA_DOMAIN, config_entry)
    await hass.async_block_till_done()

    return config_entry

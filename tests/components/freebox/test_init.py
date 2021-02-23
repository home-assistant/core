"""Tests for the Freebox config flow."""
from unittest.mock import Mock

from homeassistant.components.device_tracker import DOMAIN as DT_DOMAIN
from homeassistant.components.freebox.const import DOMAIN as DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ENTRY_STATE_LOADED, ENTRY_STATE_NOT_LOADED
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_UNAVAILABLE
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component

from .const import MOCK_CONFIG, MOCK_HOST, MOCK_PORT

from tests.common import MockConfigEntry


async def test_setup(hass: HomeAssistantType, router: Mock):
    """Test setup of integration."""
    assert await async_setup_component(hass, DOMAIN, MOCK_CONFIG)
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries()
    assert entries
    assert entries[0].data[CONF_HOST] == MOCK_HOST
    assert entries[0].data[CONF_PORT] == MOCK_PORT
    assert router.call_count == 1
    assert router().open.call_count == 1


async def test_unload_remove(hass: HomeAssistantType, router: Mock):
    """Test unload and remove of integration."""
    entity_id_dt = f"{DT_DOMAIN}.freebox_server_r2"
    entity_id_sensor = f"{SENSOR_DOMAIN}.freebox_download_speed"
    entity_id_switch = f"{SWITCH_DOMAIN}.freebox_wifi"

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG[DOMAIN],
    )
    entry.add_to_hass(hass)

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert entry is config_entries[0]

    assert await async_setup_component(hass, DOMAIN, {}) is True
    await hass.async_block_till_done()

    assert entry.state == ENTRY_STATE_LOADED
    state_dt = hass.states.get(entity_id_dt)
    assert state_dt
    state_sensor = hass.states.get(entity_id_sensor)
    assert state_sensor
    state_switch = hass.states.get(entity_id_switch)
    assert state_switch

    await hass.config_entries.async_unload(entry.entry_id)

    assert router().close.call_count == 1
    assert entry.state == ENTRY_STATE_NOT_LOADED
    state_dt = hass.states.get(entity_id_dt)
    assert state_dt.state == STATE_UNAVAILABLE
    state_sensor = hass.states.get(entity_id_sensor)
    assert state_sensor.state == STATE_UNAVAILABLE
    state_switch = hass.states.get(entity_id_switch)
    assert state_switch.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert router().close.call_count == 1
    assert entry.state == ENTRY_STATE_NOT_LOADED
    state_dt = hass.states.get(entity_id_dt)
    assert state_dt is None
    state_sensor = hass.states.get(entity_id_sensor)
    assert state_sensor is None
    state_switch = hass.states.get(entity_id_switch)
    assert state_switch is None

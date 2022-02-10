"""Tests for WiZ binary_sensor platform."""

from pywizlight import PilotParser

from homeassistant import config_entries
from homeassistant.components import wiz
from homeassistant.components.wiz.binary_sensor import OCCUPANCY_UNIQUE_ID
from homeassistant.const import CONF_HOST, STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import FAKE_IP, FAKE_MAC, _mocked_wizlight, _patch_discovery, _patch_wizlight

from tests.common import MockConfigEntry


async def test_binary_sensor_created_from_push_updates(hass: HomeAssistant) -> None:
    """Test a binary sensor created from push updates."""
    entry = MockConfigEntry(
        domain=wiz.DOMAIN,
        unique_id=FAKE_MAC,
        data={CONF_HOST: FAKE_IP},
    )
    entry.add_to_hass(hass)
    bulb = _mocked_wizlight(None, None, None)
    with _patch_discovery(), _patch_wizlight(device=bulb):
        await async_setup_component(hass, wiz.DOMAIN, {wiz.DOMAIN: {}})
        await hass.async_block_till_done()

    bulb.status = True
    bulb.state = PilotParser(
        {
            "mac": "a8bb50d46a1c",
            "src": "pir",
            "state": True,
        }
    )
    bulb.push_callback(bulb.state)
    await hass.async_block_till_done()

    entity_id = "binary_sensor.mock_title_occupancy"
    entity_registry = er.async_get(hass)
    assert entity_registry.async_get(entity_id).unique_id == f"{FAKE_MAC}_occupancy"
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    bulb.status = False
    bulb.state = PilotParser(
        {
            "mac": "a8bb50d46a1c",
            "src": "pir",
            "state": False,
        }
    )
    bulb.push_callback(bulb.state)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_binary_sensor_restored_from_registry(hass: HomeAssistant) -> None:
    """Test a binary sensor restored from registry with state unknown."""
    entry = MockConfigEntry(
        domain=wiz.DOMAIN,
        unique_id=FAKE_MAC,
        data={CONF_HOST: FAKE_IP},
    )
    entry.add_to_hass(hass)
    bulb = _mocked_wizlight(None, None, None)

    entity_registry = er.async_get(hass)
    reg_ent = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR, wiz.DOMAIN, OCCUPANCY_UNIQUE_ID.format(bulb.mac)
    )
    entity_id = reg_ent.entity_id

    with _patch_discovery(), _patch_wizlight(device=bulb):
        await async_setup_component(hass, wiz.DOMAIN, {wiz.DOMAIN: {}})
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN

    bulb.status = True
    bulb.state = PilotParser(
        {
            "mac": "a8bb50d46a1c",
            "src": "pir",
            "state": True,
        }
    )
    bulb.push_callback(bulb.state)
    await hass.async_block_till_done()

    assert entity_registry.async_get(entity_id).unique_id == f"{FAKE_MAC}_occupancy"
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == config_entries.ConfigEntryState.NOT_LOADED


async def test_binary_sensor_never_created_no_error_on_unload(
    hass: HomeAssistant,
) -> None:
    """Test a binary sensor does not error on unload."""
    entry = MockConfigEntry(
        domain=wiz.DOMAIN,
        unique_id=FAKE_MAC,
        data={CONF_HOST: FAKE_IP},
    )
    entry.add_to_hass(hass)
    bulb = _mocked_wizlight(None, None, None)

    with _patch_discovery(), _patch_wizlight(device=bulb):
        await async_setup_component(hass, wiz.DOMAIN, {wiz.DOMAIN: {}})
        await hass.async_block_till_done()

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == config_entries.ConfigEntryState.NOT_LOADED

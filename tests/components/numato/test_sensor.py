"""Tests for the numato sensor platform."""
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.helpers import discovery
from homeassistant.setup import async_setup_component

from .common import NUMATO_CFG, mockup_raise

MOCKUP_ENTITY_IDS = {
    "sensor.numato_adc_mock_port1",
}


async def test_failing_setups_no_entities(hass, numato_fixture, monkeypatch):
    """When port setup fails, no entity shall be created."""
    monkeypatch.setattr(numato_fixture.NumatoDeviceMock, "setup", mockup_raise)
    assert await async_setup_component(hass, "numato", NUMATO_CFG)
    await hass.async_block_till_done()
    for entity_id in MOCKUP_ENTITY_IDS:
        assert entity_id not in hass.states.async_entity_ids()


async def test_failing_sensor_update(hass, numato_fixture, monkeypatch):
    """Test condition when a sensor update fails."""
    monkeypatch.setattr(numato_fixture.NumatoDeviceMock, "adc_read", mockup_raise)
    assert await async_setup_component(hass, "numato", NUMATO_CFG)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.numato_adc_mock_port1").state is STATE_UNKNOWN


async def test_sensor_setup_without_discovery_info(hass, config, numato_fixture):
    """Test handling of empty discovery_info."""
    numato_fixture.discover()
    await discovery.async_load_platform(hass, Platform.SENSOR, "numato", None, config)
    for entity_id in MOCKUP_ENTITY_IDS:
        assert entity_id not in hass.states.async_entity_ids()
    await hass.async_block_till_done()  # wait for numato platform to be loaded
    for entity_id in MOCKUP_ENTITY_IDS:
        assert entity_id in hass.states.async_entity_ids()

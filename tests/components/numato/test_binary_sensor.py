"""Tests for the numato binary_sensor platform."""
from homeassistant.helpers import discovery
from homeassistant.setup import async_setup_component

from .common import NUMATO_CFG, mockup_raise

MOCKUP_ENTITY_IDS = {
    "binary_sensor.numato_binary_sensor_mock_port2",
    "binary_sensor.numato_binary_sensor_mock_port3",
    "binary_sensor.numato_binary_sensor_mock_port4",
}


async def test_failing_setups_no_entities(hass, numato_fixture, monkeypatch):
    """When port setup fails, no entity shall be created."""
    monkeypatch.setattr(numato_fixture.NumatoDeviceMock, "setup", mockup_raise)
    assert await async_setup_component(hass, "numato", NUMATO_CFG)
    await hass.async_block_till_done()
    for entity_id in MOCKUP_ENTITY_IDS:
        assert entity_id not in hass.states.async_entity_ids()


async def test_setup_callbacks(hass, numato_fixture, monkeypatch):
    """During setup a callback shall be registered."""

    numato_fixture.discover()

    def mock_add_event_detect(self, port, callback, direction):
        assert self == numato_fixture.devices[0]
        assert port == 1
        assert callback is callable
        assert direction == numato_fixture.BOTH

    monkeypatch.setattr(
        numato_fixture.devices[0], "add_event_detect", mock_add_event_detect
    )
    assert await async_setup_component(hass, "numato", NUMATO_CFG)


async def test_hass_binary_sensor_notification(hass, numato_fixture):
    """Test regular operations from within Home Assistant."""
    assert await async_setup_component(hass, "numato", NUMATO_CFG)
    await hass.async_block_till_done()  # wait until services are registered
    assert (
        hass.states.get("binary_sensor.numato_binary_sensor_mock_port2").state == "on"
    )
    await hass.async_add_executor_job(numato_fixture.devices[0].callbacks[2], 2, False)
    await hass.async_block_till_done()
    assert (
        hass.states.get("binary_sensor.numato_binary_sensor_mock_port2").state == "off"
    )


async def test_binary_sensor_setup_without_discovery_info(hass, config, numato_fixture):
    """Test handling of empty discovery_info."""
    numato_fixture.discover()
    await discovery.async_load_platform(hass, "binary_sensor", "numato", None, config)
    for entity_id in MOCKUP_ENTITY_IDS:
        assert entity_id not in hass.states.async_entity_ids()
    await hass.async_block_till_done()  # wait for numato platform to be loaded
    for entity_id in MOCKUP_ENTITY_IDS:
        assert entity_id in hass.states.async_entity_ids()

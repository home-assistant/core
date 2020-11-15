"""Test Verisure ethernet status."""
from contextlib import contextmanager

from homeassistant.components.verisure import DOMAIN as VERISURE_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.setup import async_setup_component

from tests.async_mock import patch

CONFIG = {
    "verisure": {
        "username": "test",
        "password": "test",
        "alarm": False,
        "door_window": False,
        "hygrometers": False,
        "mouse": False,
        "smartplugs": False,
        "thermometers": False,
        "smartcam": False,
    }
}


@contextmanager
def mock_hub(config, response):
    """Extensively mock out a verisure hub."""
    hub_prefix = "homeassistant.components.verisure.binary_sensor.hub"
    verisure_prefix = "verisure.Session"
    with patch(verisure_prefix) as session, patch(hub_prefix) as hub:
        session.login.return_value = True

        hub.config = config["verisure"]
        hub.get.return_value = response
        hub.get_first.return_value = response.get("ethernetConnectedNow", None)

        yield hub


async def setup_verisure(hass, config, response):
    """Set up mock verisure."""
    with mock_hub(config, response):
        await async_setup_component(hass, VERISURE_DOMAIN, config)
        await hass.async_block_till_done()


async def test_verisure_no_ethernet_status(hass):
    """Test no data from API."""
    await setup_verisure(hass, CONFIG, {})
    assert len(hass.states.async_all()) == 1
    entity_id = hass.states.async_entity_ids()[0]
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_verisure_ethernet_status_disconnected(hass):
    """Test disconnected."""
    await setup_verisure(hass, CONFIG, {"ethernetConnectedNow": False})
    assert len(hass.states.async_all()) == 1
    entity_id = hass.states.async_entity_ids()[0]
    assert hass.states.get(entity_id).state == "off"


async def test_verisure_ethernet_status_connected(hass):
    """Test connected."""
    await setup_verisure(hass, CONFIG, {"ethernetConnectedNow": True})
    assert len(hass.states.async_all()) == 1
    entity_id = hass.states.async_entity_ids()[0]
    assert hass.states.get(entity_id).state == "on"

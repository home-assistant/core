"""Test the WireGuard binary_sensor platform."""
from unittest.mock import patch

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.wireguard.const import DEFAULT_HOST, DOMAIN
from homeassistant.const import ATTR_DEVICE_CLASS, CONF_HOST
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from .conftest import mocked_requests

from tests.common import MockConfigEntry


async def test_entity_registry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the devices are registered in the entity registry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="UNIQUE_TEST_ID",
        data={CONF_HOST: DEFAULT_HOST},
    )
    config_entry.add_to_hass(hass)

    with patch("requests.get", side_effect=mocked_requests):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][config_entry.entry_id]
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    entry1: er.RegistryEntry = entity_registry.async_get(
        "binary_sensor.dummy_connectivity"
    )
    assert entry1.unique_id == "Dummy_connected"
    assert entry1.original_name == "Connectivity"

    state1: State = hass.states.get("binary_sensor.dummy_connectivity")
    assert state1
    assert state1.state == "off"
    assert state1.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.CONNECTIVITY

"""Tests for Flic button integration."""
from unittest import mock

from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component


class _MockFlicClient:
    def __init__(self, button_addresses):
        self.addresses = button_addresses
        self.get_info_callback = None
        self.scan_wizard = None

    def close(self):
        pass

    def get_info(self, callback):
        self.get_info_callback = callback
        callback({"bd_addr_of_verified_buttons": self.addresses})

    def handle_events(self):
        pass

    def add_scan_wizard(self, wizard):
        self.scan_wizard = wizard

    def add_connection_channel(self, channel):
        self.channel = channel


async def test_button_uid(hass):
    """Test UID assignment for Flic buttons."""
    address_to_name = {
        "80:e4:da:78:6e:11": "binary_sensor.flic_80e4da786e11",
        # Uppercase address should not change uid.
        "80:E4:DA:78:6E:12": "binary_sensor.flic_80e4da786e12",
    }

    flic_client = _MockFlicClient(tuple(address_to_name))

    with mock.patch.multiple(
        "pyflic",
        FlicClient=lambda _, __: flic_client,
        ButtonConnectionChannel=mock.DEFAULT,
        ScanWizard=mock.DEFAULT,
    ):
        assert await async_setup_component(
            hass,
            "binary_sensor",
            {"binary_sensor": [{"platform": "flic"}]},
        )

        await hass.async_block_till_done()

        entity_registry = er.async_get(hass)
        for address, name in address_to_name.items():
            state = hass.states.get(name)
            assert state
            assert state.attributes.get("address") == address

            entry = entity_registry.async_get(name)
            assert entry
            assert entry.unique_id == address.lower()

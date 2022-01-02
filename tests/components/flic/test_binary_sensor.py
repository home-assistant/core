"""Tests for Flic button integration."""
from unittest import mock

from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component


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
        assert isinstance(wizard, _MockScanWizard)
        self.scan_wizard = wizard

    def add_connection_channel(self, channel):
        assert channel is None


class _MockScanWizard:
    on_completed = None


async def test_button_uid(hass):
    """Test UID assignment for Flic buttons."""
    address_to_uid = {
        "80:e4:da:78:6e:11": "flic_80e4da786e11",
        "80:E4:DA:78:6E:12": "flic_80e4da786e12",  # Uppercase address should not change uid.
    }

    flic_client = _MockFlicClient(tuple(address_to_uid))

    with mock.patch(
        "homeassistant.components.flic.binary_sensor.FlicClient",
        lambda _, __: flic_client,
    ), mock.patch(
        "homeassistant.components.flic.binary_sensor.FlicButton._create_channel",
        lambda _: None,
    ), mock.patch(
        "homeassistant.components.flic.binary_sensor.ScanWizard",
        _MockScanWizard,
    ), assert_setup_component(
        1, "binary_sensor"
    ):
        assert await async_setup_component(
            hass,
            "binary_sensor",
            {"binary_sensor": [{"platform": "flic"}]},
        )

        await hass.async_block_till_done()

        assert hass.states.async_entity_ids("binary_sensor") == [
            f"binary_sensor.{uid}" for uid in address_to_uid.values()
        ]

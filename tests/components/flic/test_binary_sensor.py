"""Tests for Flic button integration."""
from unittest import mock

from homeassistant.components.flic.binary_sensor import FlicButton


class _MockFlicClient:
    def add_connection_channel(self, channel):
        assert channel is None


async def test_button_uid(hass):
    """Test UID assignment for Flic buttons."""
    address_to_uid = {
        "80:e4:da:78:6e:11": "flic_80e4da786e11",
        "80:E4:DA:78:6E:11": "flic_80e4da786e11",  # Uppercase address should not change uid.
    }
    client = _MockFlicClient()
    timeout = ignored_click_types = None

    for address, expected_uid in address_to_uid.items():
        with mock.patch(
            "homeassistant.components.flic.binary_sensor.FlicButton._create_channel",
            lambda _: None,
        ):
            button = FlicButton(hass, client, address, timeout, ignored_click_types)
            assert button.unique_id == expected_uid

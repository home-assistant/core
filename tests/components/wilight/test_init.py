"""Tests for the WiLight integration."""
from asynctest import patch
import pytest
import pywilight

from homeassistant.components.wilight.const import DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.helpers.typing import HomeAssistantType

from tests.components.wilight import HOST, setup_integration


@pytest.fixture(name="dummy_create_api_device")
def mock_dummy_create_api_device():
    """Mock a valid api_devce."""

    class Dummy:
        async def status(self, index=None):
            pass

        async def turn_on(self, index=None):
            pass

        async def turn_off(self, index=None):
            pass

        async def set_brightness(self, index=None, brightness=None):
            pass

        async def set_hs_color(self, index=None, hue=None, saturation=None):
            pass

        async def set_hsb_color(
            self, index=None, hue=None, saturation=None, brightness=None
        ):
            pass

        def stop(self):
            pass

        @property
        def is_connected(self):
            return True

    device = pywilight.discovery.wilight_from_model_serial_and_location(
        f"http://{HOST}:45995/wilight.xml",
        "5C:CF:7F:8B:CA:56",
        "WiLight 0105001800020009-00000000002510",
        "000000000090",
        "123456789012345678901234567890123456",
    )

    device.set_dummy(Dummy())

    with patch(
        "homeassistant.components.wilight.parent_device.create_api_device",
        return_value=device,
    ):
        yield device


async def test_config_entry_not_ready(hass: HomeAssistantType) -> None:
    """Test the WiLight configuration entry not ready."""
    entry = await setup_integration(hass)

    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_unload_config_entry(
    hass: HomeAssistantType, dummy_create_api_device
) -> None:
    """Test the WiLight configuration entry unloading."""
    entry = await setup_integration(hass)

    assert entry.entry_id in hass.data[DOMAIN]
    assert entry.state == ENTRY_STATE_LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.entry_id not in hass.data[DOMAIN]
    assert entry.state == ENTRY_STATE_NOT_LOADED

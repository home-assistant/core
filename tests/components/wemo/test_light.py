"""Tests for Belkin WeMo light."""
import pytest

from homeassistant.components.wemo import light
from homeassistant.components.wemo.const import DOMAIN

from . import ConfigEntryTests, DeviceTests, SubscriptionTests

from tests.async_mock import patch
from tests.common import MockConfigEntry


@pytest.fixture
def wemo_device(request, pywemo_device, pywemo_bridge_light):
    """Create a device for testing."""
    return request.cls._new_device(
        pywemo_device=pywemo_device, pywemo_bridge_light=pywemo_bridge_light
    )


class TestWemoDimmer(ConfigEntryTests, DeviceTests, SubscriptionTests):
    """Tests for the light.WemoDimmer."""

    DEVICE_MODEL = "Dimmer"

    @staticmethod
    def _new_device(pywemo_device, **_):
        return light.WemoDimmer(pywemo_device)


class TestWemoLight(DeviceTests):
    """Tests for the light.WemoLight."""

    DEVICE_MODEL = "Bridge"

    @staticmethod
    def _new_device(pywemo_bridge_light, **_):
        return light.WemoLight(pywemo_bridge_light, None)

    def test_device_info(self, wemo_device):
        """Verify the device info."""
        assert wemo_device.device_info == {
            "name": self.DEVICE_NAME,
            "identifiers": {(DOMAIN, self.DEVICE_SERIAL_NUMBER)},
            "model": "MagicMock",
            "manufacturer": "Belkin",
        }

    async def test_async_setup_entry(
        self, hass, pywemo_device, pywemo_registry, pywemo_bridge_light
    ):
        """Test that the entity is created successfully."""
        entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
        pywemo_device.Lights = {pywemo_bridge_light.name: pywemo_bridge_light}
        with patch("pywemo.discover_devices", return_value=[pywemo_device]), patch(
            "pywemo.SubscriptionRegistry", return_value=pywemo_registry
        ):
            entry.add_to_hass(hass)
            assert await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        state = hass.states.get(f"light.{pywemo_device.name}")
        assert state is not None

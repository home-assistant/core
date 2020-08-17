"""Tests for Belkin WeMo humidifier."""

import pytest

from homeassistant.components.wemo import fan
from homeassistant.components.wemo.const import DOMAIN

from . import ConfigEntryTests, DeviceTests, SubscriptionTests


@pytest.fixture
def wemo_device(pywemo_device):
    """Create a device for the WemoHumidifier."""
    return fan.WemoHumidifier(pywemo_device)


class TestWemoHumidifier(ConfigEntryTests, DeviceTests, SubscriptionTests):
    """Tests for the fan.WemoHumidifier."""

    DEVICE_MODEL = "Humidifier"

    async def test_fan_reset_filter_service(self, hass, pywemo_device, pywemo_registry):
        """Verify the reset filter service calls reset_filter_life."""
        await self.add_entity(hass, pywemo_device, pywemo_registry)
        assert hass.services.has_service(DOMAIN, fan.SERVICE_RESET_FILTER_LIFE)

        assert await hass.services.async_call(
            DOMAIN,
            fan.SERVICE_RESET_FILTER_LIFE,
            {fan.ATTR_ENTITY_ID: f"fan.{pywemo_device.name}"},
            blocking=True,
        )
        pywemo_device.reset_filter_life.assert_called_with()

    async def test_fan_set_humidity_service(self, hass, pywemo_device, pywemo_registry):
        """Verify the set humidity service calls set_humidity."""
        await self.add_entity(hass, pywemo_device, pywemo_registry)
        assert hass.services.has_service(DOMAIN, fan.SERVICE_SET_HUMIDITY)

        assert await hass.services.async_call(
            DOMAIN,
            fan.SERVICE_SET_HUMIDITY,
            {
                fan.ATTR_ENTITY_ID: f"fan.{pywemo_device.name}",
                fan.ATTR_TARGET_HUMIDITY: "50",
            },
            blocking=True,
        )
        pywemo_device.set_humidity.assert_called_with(fan.WEMO_HUMIDITY_50)

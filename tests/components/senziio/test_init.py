"""Test for Senziio device entry registration."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.senziio import (
    DOMAIN,
    PLATFORMS,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.core import HomeAssistant

from . import A_DEVICE_ID, CONFIG_ENTRY, DEVICE_INFO, FakeSenziioDevice


async def test_async_setup_entry(hass: HomeAssistant):
    """Test registering a Senziio device."""
    CONFIG_ENTRY.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.mqtt.async_wait_for_mqtt_client",
            return_value=True,
        ),
        patch(
            "homeassistant.components.senziio.SenziioDevice",
            return_value=FakeSenziioDevice(DEVICE_INFO),
        ),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", return_value=AsyncMock()
        ) as forward_entry_mock,
    ):
        # verify entry is forwarded to platforms
        assert await async_setup_entry(hass, CONFIG_ENTRY) is True
        forward_entry_mock.assert_awaited_once_with(CONFIG_ENTRY, PLATFORMS)

    device = hass.data[DOMAIN][CONFIG_ENTRY.entry_id]

    assert device is not None
    assert device.device_id == A_DEVICE_ID


async def test_do_not_setup_entry_if_mqtt_is_not_available(hass: HomeAssistant):
    """Test behavior without MQTT integration enabled."""
    CONFIG_ENTRY.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.mqtt.async_wait_for_mqtt_client",
            return_value=False,
        ),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", return_value=AsyncMock()
        ) as forward_entry_mock,
    ):
        assert await async_setup_entry(hass, CONFIG_ENTRY) is False
        forward_entry_mock.assert_not_awaited()


async def test_async_unload_entry(hass: HomeAssistant):
    """Test unloading a Senziio entry."""
    CONFIG_ENTRY.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.mqtt.async_wait_for_mqtt_client",
            return_value=True,
        ),
        patch(
            "homeassistant.components.senziio.SenziioDevice",
            return_value=FakeSenziioDevice(DEVICE_INFO),
        ),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", return_value=AsyncMock()
        ),
        patch.object(
            hass.config_entries, "async_unload_platforms", return_value=True
        ) as unload_platforms_mock,
    ):
        await async_setup_entry(hass, CONFIG_ENTRY)
        assert CONFIG_ENTRY.entry_id in hass.data[DOMAIN]

        # verify entry is correctly unloaded
        assert await async_unload_entry(hass, CONFIG_ENTRY) is True
        assert CONFIG_ENTRY.entry_id not in hass.data[DOMAIN]
        unload_platforms_mock.assert_called_once_with(CONFIG_ENTRY, PLATFORMS)

"""Test for Senziio device entry registration."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.senziio import (
    DOMAIN,
    PLATFORMS,
    MQTTError,
    SenziioHAMQTT,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

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
            "homeassistant.components.senziio.Senziio",
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
            "homeassistant.components.senziio.Senziio",
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


async def test_senziio_ha_mqtt_publish_success(hass):
    """Test successful MQTT publish."""
    mqtt_interface = SenziioHAMQTT(hass)

    with patch(
        "homeassistant.components.senziio.async_publish", new_callable=AsyncMock
    ) as publish_mock:
        await mqtt_interface.publish("test/topic", "test payload")
        publish_mock.assert_awaited_with(hass, "test/topic", "test payload")


async def test_senziio_ha_mqtt_publish_failure(hass):
    """Test failure in MQTT publish."""
    mqtt_interface = SenziioHAMQTT(hass)

    with (
        patch(
            "homeassistant.components.senziio.async_publish",
            side_effect=HomeAssistantError,
        ),
        pytest.raises(MQTTError),
    ):
        await mqtt_interface.publish("test/topic", "test payload")


async def test_senziio_ha_mqtt_subscribe_success(hass):
    """Test success when subscribing to MQTT topic."""
    mqtt_interface = SenziioHAMQTT(hass)
    callback = AsyncMock()

    with patch(
        "homeassistant.components.senziio.async_subscribe",
        new_callable=AsyncMock,
    ) as subscribe_mock:
        await mqtt_interface.subscribe("test/topic", callback)
        subscribe_mock.assert_awaited_with(hass, "test/topic", callback)


async def test_senziio_ha_mqtt_subscribe_failure(hass):
    """Test exception raised when subscribing to MQTT topic."""
    mqtt_interface = SenziioHAMQTT(hass)
    callback = AsyncMock()

    with (
        patch(
            "homeassistant.components.senziio.async_subscribe",
            side_effect=HomeAssistantError,
        ),
        pytest.raises(MQTTError),
    ):
        await mqtt_interface.subscribe("test/topic", callback)

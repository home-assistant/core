"""Testing device module of Senziio integration."""

from unittest.mock import AsyncMock, patch

import pytest
from senziio import Senziio

from homeassistant.components.senziio.device import SenziioDevice, SenziioHAMQTT
from homeassistant.components.senziio.exceptions import MQTTNotEnabled
from homeassistant.exceptions import HomeAssistantError

from . import A_DEVICE_ID, A_DEVICE_MODEL


async def test_senziio_device_initialization(hass):
    """Test initialization of Senziio device."""
    device = SenziioDevice(A_DEVICE_ID, A_DEVICE_MODEL, hass)
    assert isinstance(device, Senziio)


async def test_senziio_ha_mqtt_publish_success(hass):
    """Test successful MQTT publish."""
    mqtt_interface = SenziioHAMQTT(hass)

    with patch(
        "homeassistant.components.senziio.device.async_publish", new_callable=AsyncMock
    ) as publish_mock:
        await mqtt_interface.publish("test/topic", "test payload")
        publish_mock.assert_awaited_with(hass, "test/topic", "test payload")


async def test_senziio_ha_mqtt_publish_failure(hass):
    """Test failure in MQTT publish."""
    mqtt_interface = SenziioHAMQTT(hass)

    with (
        patch(
            "homeassistant.components.senziio.device.async_publish",
            side_effect=HomeAssistantError,
        ),
        pytest.raises(MQTTNotEnabled),
    ):
        await mqtt_interface.publish("test/topic", "test payload")


async def test_senziio_ha_mqtt_subscribe_success(hass):
    """Test success when subscribing to MQTT topic."""
    mqtt_interface = SenziioHAMQTT(hass)
    callback = AsyncMock()

    with patch(
        "homeassistant.components.senziio.device.async_subscribe",
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
            "homeassistant.components.senziio.device.async_subscribe",
            side_effect=HomeAssistantError,
        ),
        pytest.raises(MQTTNotEnabled),
    ):
        await mqtt_interface.subscribe("test/topic", callback)

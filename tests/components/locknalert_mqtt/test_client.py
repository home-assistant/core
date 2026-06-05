"""Tests for locknalert_mqtt client module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.locknalert_mqtt.client import (
    async_publish,
    async_subscribe_internal,
    publish,
)
from homeassistant.components.locknalert_mqtt.const import DOMAIN
from homeassistant.components.locknalert_mqtt.models import DATA_MQTT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.typing import MqttMockHAClientGenerator


# ---------------------------------------------------------------------------
# publish (fire-and-forget wrapper)
# ---------------------------------------------------------------------------


async def test_publish_creates_task(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """publish() schedules an async_publish task without awaiting it."""
    await mqtt_mock_entry()
    with patch(
        "homeassistant.components.locknalert_mqtt.client.async_publish",
        new_callable=AsyncMock,
    ) as mock_async_publish:
        publish(hass, "home/topic", "payload")
        await hass.async_block_till_done()
    mock_async_publish.assert_called_once_with(
        hass, "home/topic", "payload", 0, False, "utf-8"
    )


# ---------------------------------------------------------------------------
# async_publish
# ---------------------------------------------------------------------------


async def test_async_publish_not_configured_raises(hass: HomeAssistant) -> None:
    """async_publish raises HomeAssistantError when integration is not set up."""
    with pytest.raises(HomeAssistantError, match="mqtt_not_setup_cannot_publish"):
        await async_publish(hass, "test/topic", "payload")


async def test_async_publish_no_encoding_non_bytes_logs_error(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Non-bytes payload with encoding=None logs an error and returns without publishing."""
    import logging

    await mqtt_mock_entry()
    with caplog.at_level(logging.ERROR, logger="homeassistant.components.locknalert_mqtt"):
        await async_publish(hass, "test/topic", "payload", encoding=None)
    assert "no encoding set" in caplog.text


async def test_async_publish_invalid_encoding_logs_error(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Invalid encoding name logs an error and returns without publishing."""
    import logging

    await mqtt_mock_entry()
    with caplog.at_level(logging.ERROR, logger="homeassistant.components.locknalert_mqtt"):
        await async_publish(hass, "test/topic", "payload", encoding="nonexistent-enc")
    assert "Can't encode payload" in caplog.text


async def test_async_publish_bytes_payload_sent_directly(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Bytes payload is forwarded to the MQTT client without encoding."""
    mqtt_mock = await mqtt_mock_entry()
    mqtt_data = hass.data[DATA_MQTT]
    mqtt_data.client.async_publish = AsyncMock()
    await async_publish(hass, "test/topic", b"\x00\x01", qos=0, retain=False)
    mqtt_data.client.async_publish.assert_called_once_with(
        "test/topic", b"\x00\x01", 0, False
    )


async def test_async_publish_none_payload_sent_directly(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """None payload is forwarded to the MQTT client as-is."""
    await mqtt_mock_entry()
    mqtt_data = hass.data[DATA_MQTT]
    mqtt_data.client.async_publish = AsyncMock()
    await async_publish(hass, "test/topic", None, qos=0, retain=False)
    mqtt_data.client.async_publish.assert_called_once_with("test/topic", None, 0, False)


async def test_async_publish_non_default_encoding(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """String payload is encoded with the requested non-default encoding."""
    await mqtt_mock_entry()
    mqtt_data = hass.data[DATA_MQTT]
    mqtt_data.client.async_publish = AsyncMock()
    await async_publish(hass, "test/topic", "hello", encoding="utf-16")
    mqtt_data.client.async_publish.assert_called_once()
    call_args = mqtt_data.client.async_publish.call_args[0]
    assert call_args[1] == "hello".encode("utf-16")


# ---------------------------------------------------------------------------
# async_subscribe_internal
# ---------------------------------------------------------------------------


async def test_async_subscribe_internal_raises_when_not_configured(
    hass: HomeAssistant,
) -> None:
    """Raises HomeAssistantError when DATA_MQTT is not in hass.data."""
    callback = MagicMock()
    with pytest.raises(HomeAssistantError, match="mqtt_not_setup_cannot_subscribe"):
        async_subscribe_internal(hass, "test/topic", callback)


async def test_async_subscribe_internal_raises_when_entry_disabled(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Raises HomeAssistantError when the config entry is disabled."""
    await mqtt_mock_entry()
    callback = MagicMock()
    with patch(
        "homeassistant.components.locknalert_mqtt.client.mqtt_config_entry_enabled",
        return_value=False,
    ):
        with pytest.raises(HomeAssistantError, match="mqtt_not_setup_cannot_subscribe"):
            async_subscribe_internal(hass, "test/topic", callback)


async def test_async_subscribe_internal_returns_unsubscribe(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Returns a callable that unsubscribes from the topic."""
    await mqtt_mock_entry()
    callback = MagicMock()
    unsub = async_subscribe_internal(hass, "test/topic", callback)
    assert callable(unsub)
    unsub()


# ---------------------------------------------------------------------------
# MQTT.async_publish MQTTError translation
# ---------------------------------------------------------------------------


async def test_mqtt_async_publish_raises_ha_error_on_mqtt_error(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """MQTTError from broker is translated to HomeAssistantError."""
    from aiolocknalert.client import MQTTError

    await mqtt_mock_entry()

    with patch(
        "aiolocknalert.client.MQTT.async_publish",
        new_callable=AsyncMock,
        side_effect=MQTTError("broker rejected publish"),
    ):
        with pytest.raises(HomeAssistantError):
            await async_publish(hass, "test/topic", "payload")

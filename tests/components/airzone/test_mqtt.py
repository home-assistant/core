"""Tests for Airzone MQTT updates."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from aioairzone.const import AZD_MQTT, AZD_ONLINE
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.airzone.const import CONF_MQTT_TOPIC, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .util import CONFIG

MQTT_TOPIC = "test/airzone"


async def _async_setup_airzone(
    hass: HomeAssistant,
    mqtt_topic: str,
    expected_state: ConfigEntryState = ConfigEntryState.LOADED,
) -> MockConfigEntry:
    """Set up Airzone without HTTP requests."""
    entry = MockConfigEntry(
        minor_version=2,
        domain=DOMAIN,
        data=CONFIG,
        options={
            CONF_MQTT_TOPIC: mqtt_topic,
        },
        unique_id="airzone_unique_id",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.update",
        return_value=None,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is expected_state

    return entry


async def test_mqtt_messages_and_unload(
    hass: HomeAssistant,
) -> None:
    """Subscribe, process MQTT updates, request status, and unsubscribe."""
    unsubscribe = Mock()
    message_callback = None

    async def mock_subscribe(_hass, topic, callback, *, encoding):
        nonlocal message_callback

        message_callback = callback

        await callback(
            SimpleNamespace(
                topic=f"{MQTT_TOPIC}/v1/online", payload=b'{"online": true}'
            )
        )

        return unsubscribe

    async def mock_publish(_hass, topic, payload, *, qos):
        await message_callback(
            SimpleNamespace(
                topic=f"{MQTT_TOPIC}/v1/aioairzone_request/get_status",
                payload=b'{"headers": {}, "body": {"devices": []}}',
            )
        )

    with (
        patch(
            "homeassistant.components.airzone.mqtt.async_wait_for_mqtt_client",
            return_value=True,
        ) as mock_wait,
        patch(
            "homeassistant.components.airzone.mqtt.async_subscribe",
            side_effect=mock_subscribe,
        ) as mock_subscribe_call,
        patch(
            "homeassistant.components.airzone.mqtt.async_publish",
            side_effect=mock_publish,
        ) as mock_publish_call,
    ):
        entry = await _async_setup_airzone(hass, MQTT_TOPIC)
        coordinator = entry.runtime_data

        assert message_callback is not None

        mock_wait.assert_awaited_once_with(hass)
        mock_subscribe_call.assert_awaited_once()
        mock_publish_call.assert_awaited_once()

        assert coordinator.airzone.mqtt.event_online.is_set()
        assert coordinator.airzone.mqtt.event_status.is_set()
        assert coordinator.data[AZD_MQTT][AZD_ONLINE] is True

        listener = Mock()
        remove_listener = coordinator.async_add_listener(listener)
        await message_callback(
            SimpleNamespace(
                topic=f"{MQTT_TOPIC}/v1/online", payload='{"online": false}'
            )
        )
        assert coordinator.data[AZD_MQTT][AZD_ONLINE] is False
        listener.assert_called_once_with()
        remove_listener()

        with patch(
            "homeassistant.components.airzone.AirzoneMqttUpdate",
            side_effect=IndexError,
        ):
            await message_callback(
                SimpleNamespace(topic=f"{MQTT_TOPIC}/v1/online", payload=b"{}")
            )

        assert await hass.config_entries.async_unload(entry.entry_id)

        unsubscribe.assert_called_once_with()


async def test_mqtt_client_not_available(hass: HomeAssistant) -> None:
    """Test setup is retried when the MQTT client is not available."""
    with patch(
        "homeassistant.components.airzone.mqtt.async_wait_for_mqtt_client",
        return_value=False,
    ) as mock_wait:
        await _async_setup_airzone(
            hass,
            MQTT_TOPIC,
            expected_state=ConfigEntryState.SETUP_RETRY,
        )

    mock_wait.assert_awaited_once_with(hass)


@pytest.mark.parametrize("exception", [HomeAssistantError, TimeoutError])
async def test_mqtt_subscribe_failure(
    hass: HomeAssistant,
    exception: type[Exception],
) -> None:
    """Test setup is retried when subscribing to MQTT fails."""
    with (
        patch(
            "homeassistant.components.airzone.mqtt.async_wait_for_mqtt_client",
            return_value=True,
        ),
        patch(
            "homeassistant.components.airzone.mqtt.async_subscribe",
            side_effect=exception,
        ) as mock_subscribe_call,
    ):
        await _async_setup_airzone(
            hass,
            MQTT_TOPIC,
            expected_state=ConfigEntryState.SETUP_RETRY,
        )

    mock_subscribe_call.assert_awaited_once()


async def test_mqtt_publish_failure(hass: HomeAssistant) -> None:
    """Test setup is retried and unsubscribed when the status request fails."""
    unsubscribe = Mock()

    async def mock_subscribe(_hass, topic, callback, *, encoding):
        await callback(
            SimpleNamespace(
                topic=f"{MQTT_TOPIC}/v1/online", payload=b'{"online": true}'
            )
        )

        return unsubscribe

    with (
        patch(
            "homeassistant.components.airzone.mqtt.async_wait_for_mqtt_client",
            return_value=True,
        ),
        patch(
            "homeassistant.components.airzone.mqtt.async_subscribe",
            side_effect=mock_subscribe,
        ),
        patch(
            "homeassistant.components.airzone.mqtt.async_publish",
            side_effect=HomeAssistantError,
        ) as mock_publish_call,
    ):
        await _async_setup_airzone(
            hass,
            MQTT_TOPIC,
            expected_state=ConfigEntryState.SETUP_RETRY,
        )

    mock_publish_call.assert_awaited_once()
    unsubscribe.assert_called_once_with()

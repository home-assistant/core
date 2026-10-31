"""Tests for the Place coordinator."""

import json
from unittest.mock import MagicMock

from place.models.device_shadow import AlarmStatus
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration, trigger_mqtt_connect, trigger_shadow_callback

from tests.common import MockConfigEntry


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_provider",
    "mock_get_iot_credentials",
)
async def test_mqtt_shadow_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test that an MQTT shadow message updates the coordinator state."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    assert coordinator.data["thing-001"].co_alarm_status is AlarmStatus.IDLE

    payload = json.dumps(
        {"state": {"reported": {"coAlarmStatus": 3, "smokeAlarmStatus": 2}}}
    ).encode()
    trigger_shadow_callback(
        mock_mqtt_client,
        "$aws/things/thing-001/shadow/update/accepted",
        payload,
    )
    await hass.async_block_till_done()

    assert coordinator.data["thing-001"].co_alarm_status is AlarmStatus.ALARM
    assert coordinator.data["thing-001"].smoke_alarm_status is AlarmStatus.PRE_ALARM
    # Unchanged field preserved
    assert coordinator.data["thing-001"].heat_alarm_status is AlarmStatus.IDLE


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_provider",
    "mock_get_iot_credentials",
)
async def test_mqtt_shadow_new_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test that a shadow message for an unknown device creates a new entry."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    assert "thing-999" not in coordinator.data

    payload = json.dumps({"state": {"reported": {"coAlarmStatus": 1}}}).encode()
    trigger_shadow_callback(
        mock_mqtt_client,
        "$aws/things/thing-999/shadow/get/accepted",
        payload,
    )
    await hass.async_block_till_done()

    assert "thing-999" in coordinator.data
    assert coordinator.data["thing-999"].co_alarm_status is AlarmStatus.TEST


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_provider",
    "mock_get_iot_credentials",
)
async def test_mqtt_non_shadow_message_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test that non-shadow MQTT messages are ignored."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    original_co = coordinator.data["thing-001"].co_alarm_status

    # Send a non-shadow message (no state.reported)
    payload = json.dumps({"connectivity": {"connected": True}}).encode()
    trigger_shadow_callback(
        mock_mqtt_client,
        "$aws/things/thing-001/shadow/update/accepted",
        payload,
    )
    await hass.async_block_till_done()

    assert coordinator.data["thing-001"].co_alarm_status is original_co


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_provider",
    "mock_get_iot_credentials",
)
async def test_listener_notified_on_shadow_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test that registered listeners are called on shadow updates."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    callback_called = []

    def on_update() -> None:
        callback_called.append(True)

    coordinator.async_add_listener(on_update)

    payload = json.dumps({"state": {"reported": {"smokeAlarmStatus": 3}}}).encode()
    trigger_shadow_callback(
        mock_mqtt_client,
        "$aws/things/thing-001/shadow/update/accepted",
        payload,
    )
    await hass.async_block_till_done()

    assert len(callback_called) == 1


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_provider",
    "mock_get_iot_credentials",
)
async def test_listener_unsubscribe(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test that unsubscribed listeners are no longer called."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    callback_called = []

    def on_update() -> None:
        callback_called.append(True)

    remove = coordinator.async_add_listener(on_update)
    remove()

    payload = json.dumps({"state": {"reported": {"smokeAlarmStatus": 3}}}).encode()
    trigger_shadow_callback(
        mock_mqtt_client,
        "$aws/things/thing-001/shadow/update/accepted",
        payload,
    )
    await hass.async_block_till_done()

    assert len(callback_called) == 0


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_provider",
    "mock_get_iot_credentials",
)
async def test_mqtt_subscribes_on_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
    mock_place_messages: MagicMock,
) -> None:
    """Test that shadow subscriptions are set up when MQTT connects."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    trigger_mqtt_connect(mock_mqtt_client)

    mock_place_messages.subscribe_shadow.assert_called_once_with("thing-001")
    mock_place_messages.publish_shadow_get.assert_called_once_with("thing-001")


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_provider",
    "mock_get_iot_credentials",
)
async def test_mqtt_malformed_topic_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test that shadow messages with malformed topics are ignored."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    original_shadows = dict(coordinator.data)

    payload = json.dumps({"state": {"reported": {"coAlarmStatus": 3}}}).encode()
    # Malformed topic — not enough segments to extract thing_name
    trigger_shadow_callback(
        mock_mqtt_client,
        "bad/topic",
        payload,
    )
    await hass.async_block_till_done()

    assert coordinator.data == original_shadows

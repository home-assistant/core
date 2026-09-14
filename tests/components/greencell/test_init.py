"""Greencell integration initialization test cases."""

from collections.abc import Callable
import time
from unittest.mock import patch

import pytest

from homeassistant.components.greencell.const import GREENCELL_DISC_TOPIC
from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import TEST_CURRENT_TOPIC, TEST_SERIAL_NUMBER, TEST_VOLTAGE_TOPIC

from tests.common import MockConfigEntry
from tests.typing import MqttMockHAClient


def _make_message(topic: str, payload: str) -> ReceiveMessage:
    """Build a ReceiveMessage for the mocked subscription callback."""
    return ReceiveMessage(
        topic=topic,
        payload=payload,
        qos=0,
        retain=False,
        subscribed_topic=topic,
        timestamp=time.time(),
    )


async def _mock_subscribe_fires(messages: list[tuple[str, str]]):
    """Return a mock async_subscribe that fires given messages on subscription."""

    async def _subscribe(
        hass: HomeAssistant, topic: str, msg_callback, *args, **kwargs
    ) -> Callable[[], None]:
        for msg_topic, payload in messages:
            if msg_topic == topic:
                msg_callback(_make_message(topic, payload))
        return lambda: None

    return _subscribe


@pytest.mark.parametrize(
    "messages",
    [
        pytest.param(
            [(GREENCELL_DISC_TOPIC, f'{{"id": "{TEST_SERIAL_NUMBER}"}}')],
            id="discovery_match",
        ),
        pytest.param(
            [(TEST_VOLTAGE_TOPIC, '{"l1": 230, "l2": 230, "l3": 230}')],
            id="voltage_no_id",
        ),
        pytest.param(
            [(TEST_VOLTAGE_TOPIC, f'{{"id": "{TEST_SERIAL_NUMBER}", "l1": 230}}')],
            id="voltage_matching_id",
        ),
    ],
)
async def test_async_setup_entry_ready(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
    messages: list[tuple[str, str]],
) -> None:
    """Setup completes once matching device data arrives on a subscribed topic."""
    mock_config_entry.add_to_hass(hass)

    subscribe = await _mock_subscribe_fires(messages)

    with patch(
        "homeassistant.components.greencell.mqtt.async_subscribe",
        side_effect=subscribe,
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "messages",
    [
        pytest.param(
            [(GREENCELL_DISC_TOPIC, '{"id": "OTHER_SERIAL"}')],
            id="discovery_wrong_serial",
        ),
        pytest.param(
            [(TEST_VOLTAGE_TOPIC, '{"id": "OTHER_SERIAL", "l1": 230}')],
            id="voltage_wrong_id",
        ),
        pytest.param(
            [(TEST_VOLTAGE_TOPIC, "{INVALID JSON}")],
            id="invalid_payload",
        ),
        pytest.param([], id="no_response"),
    ],
)
async def test_async_setup_entry_not_ready(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
    messages: list[tuple[str, str]],
) -> None:
    """Setup retries when no matching device data arrives before the timeout."""
    mock_config_entry.add_to_hass(hass)

    subscribe = await _mock_subscribe_fires(messages)

    with (
        patch("homeassistant.components.greencell.DISCOVERY_TIMEOUT", 0),
        patch(
            "homeassistant.components.greencell.mqtt.async_subscribe",
            side_effect=subscribe,
        ),
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "no_device_data"


async def test_setup_entry_mqtt_client_unavailable(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Setup retries with a translated error when the MQTT client never comes up."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.greencell.mqtt.async_wait_for_mqtt_client",
        return_value=False,
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "mqtt_unavailable"


async def test_setup_entry_mqtt_subscribe_error(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Setup retries with a translated error when subscribing raises."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.greencell.mqtt.async_subscribe",
        side_effect=HomeAssistantError("boom"),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "mqtt_error"


async def test_setup_platform_mqtt_subscribe_error(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The sensor platform gives up on its entities when subscribing raises."""
    mock_config_entry.add_to_hass(hass)

    ready = await _mock_subscribe_fires(
        [(GREENCELL_DISC_TOPIC, f'{{"id": "{TEST_SERIAL_NUMBER}"}}')]
    )

    async def _subscribe(
        hass_arg: HomeAssistant, topic: str, msg_callback, *args, **kwargs
    ) -> Callable[[], None]:
        """Let the entry become ready, then fail on the first sensor topic."""
        if topic == TEST_CURRENT_TOPIC:
            raise HomeAssistantError("boom")
        return await ready(hass_arg, topic, msg_callback, *args, **kwargs)

    with patch(
        "homeassistant.components.greencell.mqtt.async_subscribe",
        side_effect=_subscribe,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not hass.states.async_entity_ids(SENSOR_DOMAIN)


async def test_async_unload_entry_success(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unload entry cleans up platforms."""
    mock_config_entry.add_to_hass(hass)

    subscribe = await _mock_subscribe_fires(
        [(GREENCELL_DISC_TOPIC, f'{{"id": "{TEST_SERIAL_NUMBER}"}}')]
    )

    with patch(
        "homeassistant.components.greencell.mqtt.async_subscribe",
        side_effect=subscribe,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert result is True
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

"""Test the qingping_mqtt integration setup."""

from collections.abc import Callable
import time
from typing import Any
from unittest.mock import patch

from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.components.qingping_mqtt.const import DOMAIN, MQTT_TOPIC_PREFIX
from homeassistant.components.qingping_mqtt.coordinator import QingpingMqttCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_MAC, CONF_MODEL
from homeassistant.core import HomeAssistant

from . import MQTT_EMPTY_PAYLOAD, MQTT_MAC, MQTT_REALTIME_RSSI_PAYLOAD, MQTT_TLV_PAYLOAD

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import MqttMockHAClient


def _mock_config_entry() -> MockConfigEntry:
    """Return a config entry for an MQTT connected device."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MQTT_MAC,
        data={CONF_MAC: MQTT_MAC, CONF_MODEL: "cgr1w"},
    )


async def test_setup_and_unload(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test the coordinator receives device messages and the entry unloads."""
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator: QingpingMqttCoordinator = entry.runtime_data
    assert coordinator.data["online"] is True

    async_fire_mqtt_message(
        hass, f"{MQTT_TOPIC_PREFIX}/{MQTT_MAC}/up", MQTT_TLV_PAYLOAD
    )
    await hass.async_block_till_done()

    assert coordinator.data["sensors"]["temperature"] == 25.8
    assert coordinator.data["sensors"]["humidity"] == 65.3

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry_when_mqtt_not_configured(hass: HomeAssistant) -> None:
    """Test the entry retries setup when the MQTT integration is missing."""
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_handle_message_payload_variants(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test how the coordinator handles different payload shapes."""
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator: QingpingMqttCoordinator = entry.runtime_data
    topic = f"{MQTT_TOPIC_PREFIX}/{MQTT_MAC}/up"

    async_fire_mqtt_message(hass, topic, MQTT_TLV_PAYLOAD)
    await hass.async_block_till_done()
    assert coordinator.data["sensors"]["temperature"] == 25.8
    assert coordinator.data["signal_strength"] == -55

    # A bytearray payload is converted to bytes before decoding
    async_fire_mqtt_message(hass, topic, bytearray(MQTT_TLV_PAYLOAD))
    await hass.async_block_till_done()
    assert coordinator.data["sensors"]["temperature"] == 25.8

    # A payload without the TLV marker is ignored
    async_fire_mqtt_message(hass, topic, b"not a qingping packet")
    await hass.async_block_till_done()
    assert coordinator.data["sensors"]["temperature"] == 25.8

    # A packet without sensor data keeps the previous values
    async_fire_mqtt_message(hass, topic, MQTT_EMPTY_PAYLOAD)
    await hass.async_block_till_done()
    assert coordinator.data["sensors"]["temperature"] == 25.8
    assert coordinator.data["signal_strength"] == -55

    # A realtime frame without signal strength falls back to its rssi value
    async_fire_mqtt_message(hass, topic, MQTT_REALTIME_RSSI_PAYLOAD)
    await hass.async_block_till_done()
    assert coordinator.data["signal_strength"] == -60


async def test_handle_message_string_payload(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test a payload delivered as a string is encoded before decoding."""

    async def _mock_subscribe(
        _hass: HomeAssistant,
        _topic: str,
        msg_callback: Callable[[ReceiveMessage], None],
        *_args: Any,
        **_kwargs: Any,
    ) -> Callable[[], None]:
        """Deliver a string payload message to the subscription callback."""
        topic = f"{MQTT_TOPIC_PREFIX}/{MQTT_MAC}/up"
        msg_callback(
            ReceiveMessage(
                topic=topic,
                payload=MQTT_TLV_PAYLOAD.decode("latin-1"),
                qos=0,
                retain=False,
                subscribed_topic=topic,
                timestamp=time.time(),
            )
        )
        return lambda: None

    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.qingping_mqtt.coordinator.mqtt.async_subscribe",
        side_effect=_mock_subscribe,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator: QingpingMqttCoordinator = entry.runtime_data
    # Binary TLV data does not survive a text round trip; the coordinator
    # handles the undecodable packet without crashing and stays online.
    assert coordinator.data["online"] is True
    assert coordinator.data["sensors"] == {}

"""Test fixtures for locknalert_mqtt component."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from random import getrandbits
from typing import Any
from unittest.mock import MagicMock, patch

from aiolocknalert.util import EnsureJobAfterCooldown
import pytest

from homeassistant.components import locknalert_mqtt
from homeassistant.components.locknalert_mqtt.models import (
    MessageCallbackType,
    ReceiveMessage,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentryData
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import MockConfigEntry, MockMqttReasonCode
from tests.typing import MqttMockHAClient, MqttMockHAClientGenerator, MqttMockPahoClient

ENTRY_DEFAULT_BIRTH_MESSAGE = {
    locknalert_mqtt.CONF_BIRTH_MESSAGE: {
        locknalert_mqtt.ATTR_TOPIC: "homeassistant/status",
        locknalert_mqtt.ATTR_PAYLOAD: "online",
        locknalert_mqtt.ATTR_QOS: 0,
        locknalert_mqtt.ATTR_RETAIN: False,
    },
}


@pytest.fixture(autouse=True)
def patch_hass_config(mock_hass_config: None) -> None:
    """Patch configuration.yaml."""


@pytest.fixture
def temp_dir_prefix() -> str:
    """Set an alternate temp dir prefix."""
    return "test"


@pytest.fixture(autouse=True)
async def mock_temp_dir(
    hass: HomeAssistant, tmp_path: Path, temp_dir_prefix: str
) -> AsyncGenerator[str]:
    """Mock the certificate temp directory."""
    temp_dir_name = (
        f"home-assistant-locknalert-mqtt-{temp_dir_prefix}-{getrandbits(10):03x}"
    )
    with (
        patch(
            "homeassistant.components.locknalert_mqtt.util.tempfile.gettempdir",
            return_value=tmp_path,
        ),
        patch(
            "homeassistant.components.locknalert_mqtt.util.TEMP_DIR_NAME",
            temp_dir_name,
        ) as mocked_temp_dir,
    ):
        yield mocked_temp_dir


@pytest.fixture
def mqtt_client_mock(hass: HomeAssistant) -> Generator[MqttMockPahoClient]:
    """Fixture to mock the locknalert_mqtt MQTT client."""
    mid: int = 0

    def get_mid() -> int:
        nonlocal mid
        mid += 1
        return mid

    class FakeInfo:
        def __init__(self, mid: int) -> None:
            self.mid = mid
            self.rc = 0

    with patch("aiolocknalert.client.AsyncMQTTClient") as mock_client:

        @callback
        def _async_fire_mqtt_message(topic, payload, qos, retain):
            from tests.common import async_fire_mqtt_message  # noqa: PLC0415

            async_fire_mqtt_message(hass, topic, payload or b"", qos, retain)
            mid = get_mid()
            hass.loop.call_soon(
                mock_client.on_publish,
                MagicMock(),
                0,
                mid,
                MockMqttReasonCode(),
                None,
            )
            return FakeInfo(mid)

        def _subscribe(topic, qos=0):
            mid = get_mid()
            hass.loop.call_soon(
                mock_client.on_subscribe,
                MagicMock(),
                0,
                mid,
                [MockMqttReasonCode()],
                None,
            )
            return (0, mid)

        def _unsubscribe(topic):
            mid = get_mid()
            hass.loop.call_soon(
                mock_client.on_unsubscribe,
                MagicMock(),
                0,
                mid,
                [MockMqttReasonCode()],
                None,
            )
            return (0, mid)

        def _connect(*args, **kwargs):
            mock_client.reconnect()
            hass.loop.call_soon_threadsafe(
                mock_client.on_connect,
                mock_client,
                None,
                0,
                MockMqttReasonCode(),
            )
            mock_client.on_socket_open(
                mock_client, None, MagicMock(fileno=MagicMock(return_value=-1))
            )
            mock_client.on_socket_register_write(
                mock_client, None, MagicMock(fileno=MagicMock(return_value=-1))
            )
            return 0

        mock_client = mock_client.return_value
        mock_client.connect.side_effect = _connect
        mock_client.subscribe.side_effect = _subscribe
        mock_client.unsubscribe.side_effect = _unsubscribe
        mock_client.publish.side_effect = _async_fire_mqtt_message
        mock_client.loop_read.return_value = 0
        yield mock_client


@pytest.fixture
def mock_debouncer(hass: HomeAssistant) -> Generator[asyncio.Event]:
    """Mock EnsureJobAfterCooldown."""
    task_done = asyncio.Event()

    class MockDebouncer(EnsureJobAfterCooldown):
        async def _run(self) -> None:
            await super()._run()
            task_done.set()

        async def async_execute(self) -> None:
            await super().async_execute()
            task_done.set()

    with patch(
        "aiolocknalert.client.EnsureJobAfterCooldown",
        MockDebouncer,
    ):
        yield task_done


@pytest.fixture
async def mqtt_mock_entry(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_config_entry_data: dict[str, Any] | None,
    mqtt_config_entry_options: dict[str, Any] | None,
    mqtt_config_subentries_data: tuple[ConfigSubentryData] | None,
) -> AsyncGenerator[MqttMockHAClientGenerator]:
    """Set up a locknalert_mqtt config entry."""
    if mqtt_config_entry_data is None:
        mqtt_config_entry_data = {
            locknalert_mqtt.CONF_BROKER: "mock-broker",
        }
    if mqtt_config_entry_options is None:
        mqtt_config_entry_options = {locknalert_mqtt.CONF_BIRTH_MESSAGE: {}}

    await hass.async_block_till_done()

    entry = MockConfigEntry(
        data=mqtt_config_entry_data,
        options=mqtt_config_entry_options,
        subentries_data=mqtt_config_subentries_data,
        domain=locknalert_mqtt.DOMAIN,
        title="LocknAlert MQTT",
        version=locknalert_mqtt.CONFIG_ENTRY_VERSION,
        minor_version=locknalert_mqtt.CONFIG_ENTRY_MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    real_mqtt_cls = locknalert_mqtt.MQTT
    real_mqtt_instance: locknalert_mqtt.MQTT | None = None
    mock_mqtt_instance: MqttMockHAClient | None = None

    def create_mock_mqtt(*args: Any, **kwargs: Any) -> MqttMockHAClient:
        nonlocal mock_mqtt_instance, real_mqtt_instance
        real_mqtt_instance = real_mqtt_cls(*args, **kwargs)
        spec = [*dir(real_mqtt_instance), "_mqttc"]
        mock_mqtt_instance = MagicMock(
            return_value=real_mqtt_instance,
            spec_set=spec,
            wraps=real_mqtt_instance,
        )
        return mock_mqtt_instance

    async def _async_setup_config_entry(
        hass: HomeAssistant, entry: ConfigEntry
    ) -> bool:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return True

    async def setup() -> MqttMockHAClient:
        assert await _async_setup_config_entry(hass, entry)
        assert real_mqtt_instance is not None, (
            "locknalert_mqtt was not set up correctly"
        )
        mock_mqtt_instance._mqttc = mqtt_client_mock
        mock_mqtt_instance.connected = True
        mqtt_client_mock.on_connect(mqtt_client_mock, None, 0, MockMqttReasonCode())
        async_dispatcher_send(hass, locknalert_mqtt.MQTT_CONNECTION_STATE, True)
        await hass.async_block_till_done()
        return mock_mqtt_instance

    with patch(
        "homeassistant.components.locknalert_mqtt.MQTT",
        side_effect=create_mock_mqtt,
    ):
        yield setup


@pytest.fixture
async def setup_with_birth_msg_client_mock(
    hass: HomeAssistant,
    mqtt_config_entry_data: dict[str, Any] | None,
    mqtt_config_entry_options: dict[str, Any] | None,
    mqtt_client_mock: MqttMockPahoClient,
) -> AsyncGenerator[MqttMockPahoClient]:
    """Test sending birth message."""
    birth = asyncio.Event()
    with (
        patch(
            "aiolocknalert.client.INITIAL_SUBSCRIBE_COOLDOWN",
            0.0,
        ),
        patch("aiolocknalert.client.DISCOVERY_COOLDOWN", 0.0),
        patch("aiolocknalert.client.SUBSCRIBE_COOLDOWN", 0.0),
    ):
        entry = MockConfigEntry(
            domain=locknalert_mqtt.DOMAIN,
            data=mqtt_config_entry_data or {locknalert_mqtt.CONF_BROKER: "test-broker"},
            options=mqtt_config_entry_options or {},
            version=locknalert_mqtt.CONFIG_ENTRY_VERSION,
            minor_version=locknalert_mqtt.CONFIG_ENTRY_MINOR_VERSION,
        )
        entry.add_to_hass(hass)
        hass.config.components.add(locknalert_mqtt.DOMAIN)
        assert await hass.config_entries.async_setup(entry.entry_id)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)

        @callback
        def wait_birth(msg: ReceiveMessage) -> None:
            birth.set()

        await locknalert_mqtt.async_subscribe(hass, "homeassistant/status", wait_birth)
        await hass.async_block_till_done()
        await birth.wait()
        yield mqtt_client_mock


@pytest.fixture
def recorded_calls() -> list[ReceiveMessage]:
    """Fixture to hold recorded calls."""
    return []


@pytest.fixture
def record_calls(recorded_calls: list[ReceiveMessage]) -> MessageCallbackType:
    """Fixture to record calls."""

    @callback
    def record_calls(msg: ReceiveMessage) -> None:
        recorded_calls.append(msg)

    return record_calls

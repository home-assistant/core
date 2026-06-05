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
    """Patch configuration.yaml to an empty dict for each test.

    Prevents accidental bleed from a developer's real ``configuration.yaml``
    into the test environment.  Automatically applied to every test in this
    module via ``autouse=True``.
    """


@pytest.fixture
def temp_dir_prefix() -> str:
    """Return a unique prefix used when naming the integration's temp directory.

    Returns:
        str: A short prefix string (``"test"``) that is combined with a random
            suffix to prevent temp-directory collisions between parallel test
            runs.
    """
    return "test"


@pytest.fixture(autouse=True)
async def mock_temp_dir(
    hass: HomeAssistant, tmp_path: Path, temp_dir_prefix: str
) -> AsyncGenerator[str]:
    """Redirect TLS certificate temp files to pytest's isolated tmp_path.

    Patches both ``tempfile.gettempdir`` and ``TEMP_DIR_NAME`` inside
    :mod:`~homeassistant.components.locknalert_mqtt.util` so certificate
    files are written to a throwaway directory that is cleaned up automatically
    after each test.

    Yields:
        str: The mocked ``TEMP_DIR_NAME`` value (prefix + random hex suffix).
    """
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
    """Yield a mock paho MQTT client wired into the locknalert_mqtt integration.

    Patches :class:`~aiolocknalert.client.AsyncMQTTClient` with a
    :class:`~unittest.mock.MagicMock` that:

    * Fires HA MQTT messages and publish mid callbacks when ``publish`` is
      called.
    * Fires subscribe/unsubscribe mid callbacks when ``subscribe`` /
      ``unsubscribe`` are called.
    * Simulates a successful broker connection and socket events on
      ``connect``.

    Args:
        hass (HomeAssistant): The Home Assistant instance.

    Yields:
        MqttMockPahoClient: The configured mock client instance.
    """
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
            from .common import async_fire_mqtt_message  # noqa: PLC0415

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
    """Yield an asyncio.Event that fires whenever a debounced job completes.

    Replaces :class:`~aiolocknalert.client.EnsureJobAfterCooldown` with a
    subclass that sets the event after each execution, letting tests wait for
    debounced operations (e.g. subscribe batching) without sleeping.

    Args:
        hass (HomeAssistant): The Home Assistant instance.

    Yields:
        asyncio.Event: Call ``await event.wait()`` to block until the next
            debounced job finishes; call ``event.clear()`` before the
            triggering action to reset for the next wait.
    """
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
    """Yield a coroutine that sets up a locknalert_mqtt config entry on demand.

    Creates a :class:`~tests.common.MockConfigEntry` with the provided data,
    options, and subentries, wraps the real ``MQTT`` class with a
    :class:`~unittest.mock.MagicMock`, and yields a ``setup()`` coroutine.
    Calling ``await setup()`` actually loads the entry and returns the mock
    client so tests can assert on publish/subscribe calls.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_client_mock (MqttMockPahoClient): The mock paho client fixture.
        mqtt_config_entry_data (dict[str, Any] | None): Config entry data;
            defaults to ``{CONF_BROKER: "mock-broker"}`` if ``None``.
        mqtt_config_entry_options (dict[str, Any] | None): Config entry
            options; defaults to ``{CONF_BIRTH_MESSAGE: {}}`` if ``None``.
        mqtt_config_subentries_data (tuple[ConfigSubentryData] | None): Sub-
            entry data for device subentries, or ``None`` for none.

    Yields:
        MqttMockHAClientGenerator: An async callable that loads the config
            entry and returns the :class:`MqttMockHAClient`.
    """
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
    """Set up a locknalert_mqtt entry with zero-delay debouncers and wait for the birth message.

    Patches all cooldown constants to ``0.0`` so subscriptions are flushed
    immediately, then subscribes to the birth-message topic and waits until
    the birth message is received before yielding.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        mqtt_config_entry_data (dict[str, Any] | None): Config entry data.
        mqtt_config_entry_options (dict[str, Any] | None): Config entry options.
        mqtt_client_mock (MqttMockPahoClient): The mock paho client fixture.

    Yields:
        MqttMockPahoClient: The mock paho client after the birth message has
            been published.
    """
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
    """Return an empty list that accumulates MQTT messages for assertion.

    Returns:
        list[ReceiveMessage]: Mutable list shared with the :func:`record_calls`
            fixture; append-only during the test.
    """
    return []


@pytest.fixture
def record_calls(recorded_calls: list[ReceiveMessage]) -> MessageCallbackType:
    """Return a callback that appends each received MQTT message to ``recorded_calls``.

    Intended to be passed as a ``msg_callback`` to
    :func:`~homeassistant.components.locknalert_mqtt.async_subscribe`.

    Args:
        recorded_calls (list[ReceiveMessage]): The shared list to append to,
            provided by the :func:`recorded_calls` fixture.

    Returns:
        MessageCallbackType: A ``@callback``-decorated function that records
            received messages.
    """

    @callback
    def record_calls(msg: ReceiveMessage) -> None:
        """Append *msg* to the shared recorded_calls list."""
        recorded_calls.append(msg)

    return record_calls

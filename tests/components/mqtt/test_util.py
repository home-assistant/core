"""Test MQTT utils."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from random import getrandbits
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components import mqtt
from homeassistant.components.mqtt.models import MessageCallbackType
from homeassistant.components.mqtt.util import EnsureJobAfterCooldown
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import MqttMockHAClient, MqttMockPahoClient


async def test_canceling_debouncer_on_shutdown(
    hass: HomeAssistant,
    record_calls: MessageCallbackType,
    mock_debouncer: asyncio.Event,
    setup_with_birth_msg_client_mock: MqttMockPahoClient,
) -> None:
    """Test canceling the debouncer when HA shuts down."""
    mqtt_client_mock = setup_with_birth_msg_client_mock
    # Mock we are past initial setup
    await mock_debouncer.wait()
    with patch("homeassistant.components.mqtt.client.SUBSCRIBE_COOLDOWN", 2):
        mock_debouncer.clear()
        await mqtt.async_subscribe(hass, "test/state1", record_calls)
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=0.1))
        # Stop HA so the scheduled debouncer task will be canceled
        mqtt_client_mock.subscribe.reset_mock()
        hass.bus.fire(EVENT_HOMEASSISTANT_STOP)
        await mqtt.async_subscribe(hass, "test/state2", record_calls)
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=0.1))
        await mqtt.async_subscribe(hass, "test/state3", record_calls)
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=0.1))
        await mqtt.async_subscribe(hass, "test/state4", record_calls)
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=0.1))
        await mqtt.async_subscribe(hass, "test/state5", record_calls)
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=5))
        await hass.async_block_till_done(wait_background_tasks=True)
        # Assert the debouncer subscribe job was not executed
        assert not mock_debouncer.is_set()
        mqtt_client_mock.subscribe.assert_not_called()

        # Note thet the broker connection will not be disconnected gracefully
        await hass.async_block_till_done()
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=5))
        await asyncio.sleep(0)
        await hass.async_block_till_done(wait_background_tasks=True)
        mqtt_client_mock.subscribe.assert_not_called()
        mqtt_client_mock.disconnect.assert_not_called()


async def test_canceling_debouncer_normal(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test canceling the debouncer before completion."""

    async def _async_myjob() -> None:
        await asyncio.sleep(1.0)

    debouncer = EnsureJobAfterCooldown(0.0, _async_myjob)
    debouncer.async_schedule()
    await asyncio.sleep(0.01)
    assert debouncer._task is not None
    await debouncer.async_cleanup()
    assert debouncer._task is None


async def test_canceling_debouncer_throws(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test canceling the debouncer when HA shuts down."""

    async def _async_myjob() -> None:
        await asyncio.sleep(1.0)

    debouncer = EnsureJobAfterCooldown(0.0, _async_myjob)
    debouncer.async_schedule()
    await asyncio.sleep(0.01)
    assert debouncer._task is not None
    # let debouncer._task fail by mocking it
    with patch.object(debouncer, "_task") as task:
        task.cancel = MagicMock(return_value=True)
        await debouncer.async_cleanup()
        assert "Error cleaning up task" in caplog.text
        await hass.async_block_till_done()
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=5))
        await hass.async_block_till_done()


async def help_create_test_certificate_file(
    hass: HomeAssistant,
    mock_temp_dir: str,
    option: str,
    content: bytes = b"old content",
) -> None:
    """Help creating a certificate test file."""
    temp_dir = Path(tempfile.gettempdir()) / mock_temp_dir

    def _create_file() -> None:
        if not temp_dir.exists():
            temp_dir.mkdir(0o700)
        temp_file = temp_dir / option
        with open(temp_file, "wb") as old_file:
            old_file.write(content)
            old_file.close()

    await hass.async_add_executor_job(_create_file)


@pytest.mark.parametrize(
    ("option", "content"),
    [
        (mqtt.CONF_CERTIFICATE, "### CA CERTIFICATE ###"),
        (mqtt.CONF_CLIENT_CERT, "### CLIENT CERTIFICATE ###"),
        (mqtt.CONF_CLIENT_KEY, "### PRIVATE KEY ###"),
    ],
)
@pytest.mark.parametrize("temp_dir_prefix", ["create-test1"])
async def test_async_create_certificate_temp_files(
    hass: HomeAssistant,
    mock_temp_dir: str,
    option: str,
    content: str,
) -> None:
    """Test creating and reading and recovery certificate files."""
    config = {option: content}

    # Create old file to be able to assert it is replaced and recovered
    await help_create_test_certificate_file(hass, mock_temp_dir, option)
    await mqtt.util.async_create_certificate_temp_files(hass, config)
    file_path = await hass.async_add_executor_job(mqtt.util.get_file_path, option)
    assert file_path is not None
    assert (
        await hass.async_add_executor_job(
            mqtt.util.migrate_certificate_file_to_content, file_path
        )
        == content
    )

    # Make sure old files are removed to test certificate and dir creation
    def _remove_old_files() -> None:
        temp_dir = Path(tempfile.gettempdir()) / mock_temp_dir
        shutil.rmtree(temp_dir)

    await hass.async_add_executor_job(_remove_old_files)

    # Test a new dir and file is created correctly
    await mqtt.util.async_create_certificate_temp_files(hass, config)
    file_path = await hass.async_add_executor_job(mqtt.util.get_file_path, option)
    assert file_path is not None
    assert (
        await hass.async_add_executor_job(
            mqtt.util.migrate_certificate_file_to_content, file_path
        )
        == content
    )


@pytest.mark.parametrize("temp_dir_prefix", ["create-test2"])
async def test_certificate_temp_files_with_auto_mode(
    hass: HomeAssistant,
    mock_temp_dir: str,
) -> None:
    """Test creating and reading and recovery certificate files with auto mode."""
    config = {mqtt.CONF_CERTIFICATE: "auto"}

    # Create old file to be able to assert it is removed with auto option
    await help_create_test_certificate_file(hass, mock_temp_dir, mqtt.CONF_CERTIFICATE)
    await mqtt.util.async_create_certificate_temp_files(hass, config)
    file_path = await hass.async_add_executor_job(mqtt.util.get_file_path, "auto")
    assert file_path is None
    assert (
        await hass.async_add_executor_job(
            mqtt.util.migrate_certificate_file_to_content, "auto"
        )
        == "auto"
    )


async def test_reading_non_exitisting_certificate_file() -> None:
    """Test reading a non existing certificate file."""
    assert (
        mqtt.util.migrate_certificate_file_to_content("/home/file_not_exists") is None
    )


@pytest.mark.parametrize("temp_dir_prefix", "unknown")
async def test_return_default_get_file_path(
    hass: HomeAssistant, mock_temp_dir: str
) -> None:
    """Test get_file_path returns default."""

    def _get_file_path(file_path: Path) -> bool:
        return (
            not file_path.exists()
            and mqtt.util.get_file_path("some_option", "mydefault") == "mydefault"
        )

    with patch(
        "homeassistant.components.mqtt.util.TEMP_DIR_NAME",
        f"home-assistant-mqtt-other-{getrandbits(10):03x}",
    ) as temp_dir_name:
        tempdir = Path(tempfile.gettempdir()) / temp_dir_name
        assert await hass.async_add_executor_job(_get_file_path, tempdir)


async def test_waiting_for_client_not_loaded(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
) -> None:
    """Test waiting for client while mqtt entry is not yet loaded."""
    hass.set_state(CoreState.starting)
    await hass.async_block_till_done()

    entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        data={"broker": "test-broker"},
        state=ConfigEntryState.NOT_LOADED,
    )
    entry.add_to_hass(hass)

    unsubs: list[Callable[[], None]] = []

    async def _async_just_in_time_subscribe() -> Callable[[], None]:
        nonlocal unsub
        assert await mqtt.async_wait_for_mqtt_client(hass)
        # Awaiting a second time should work too and return True
        assert await mqtt.async_wait_for_mqtt_client(hass)
        unsubs.append(await mqtt.async_subscribe(hass, "test_topic", lambda msg: None))

    # Simulate some integration waiting for the client to become available
    for _ in range(4):
        hass.async_create_task(_async_just_in_time_subscribe())

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert len(unsubs) == 4
    for unsub in unsubs:
        unsub()


async def test_waiting_for_client_loaded(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test waiting for client where mqtt entry is loaded."""
    unsub: Callable[[], None] | None = None

    async def _async_just_in_time_subscribe() -> Callable[[], None]:
        nonlocal unsub
        assert await mqtt.async_wait_for_mqtt_client(hass)
        unsub = await mqtt.async_subscribe(hass, "test_topic", lambda msg: None)

    entry = hass.config_entries.async_entries(mqtt.DATA_MQTT)[0]
    assert entry.state is ConfigEntryState.LOADED

    await _async_just_in_time_subscribe()

    assert unsub is not None
    unsub()


async def test_waiting_for_client_entry_fails(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
) -> None:
    """Test waiting for client where mqtt entry is failing."""
    hass.set_state(CoreState.starting)
    await hass.async_block_till_done()

    entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        data={"broker": "test-broker"},
        state=ConfigEntryState.NOT_LOADED,
    )
    entry.add_to_hass(hass)

    async def _async_just_in_time_subscribe() -> Callable[[], None]:
        assert not await mqtt.async_wait_for_mqtt_client(hass)

    hass.async_create_task(_async_just_in_time_subscribe())
    assert entry.state is ConfigEntryState.NOT_LOADED
    with patch(
        "homeassistant.components.mqtt.async_setup_entry",
        side_effect=Exception,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_waiting_for_client_setup_fails(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
) -> None:
    """Test waiting for client where mqtt entry is failing during setup."""
    hass.set_state(CoreState.starting)
    await hass.async_block_till_done()

    entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        data={"broker": "test-broker"},
        state=ConfigEntryState.NOT_LOADED,
    )
    entry.add_to_hass(hass)

    async def _async_just_in_time_subscribe() -> Callable[[], None]:
        assert not await mqtt.async_wait_for_mqtt_client(hass)

    hass.async_create_task(_async_just_in_time_subscribe())
    assert entry.state is ConfigEntryState.NOT_LOADED

    # Simulate MQTT setup fails before the client would become available
    mqtt_client_mock.connect.side_effect = Exception
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR


@patch("homeassistant.components.mqtt.util.AVAILABILITY_TIMEOUT", 0.01)
async def test_waiting_for_client_timeout(
    hass: HomeAssistant,
) -> None:
    """Test waiting for client with timeout."""
    hass.set_state(CoreState.starting)
    await hass.async_block_till_done()

    entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        data={"broker": "test-broker"},
        state=ConfigEntryState.NOT_LOADED,
    )
    entry.add_to_hass(hass)

    assert entry.state is ConfigEntryState.NOT_LOADED
    # returns False after timeout
    assert not await mqtt.async_wait_for_mqtt_client(hass)


async def test_waiting_for_client_with_disabled_entry(
    hass: HomeAssistant,
) -> None:
    """Test waiting for client with timeout."""
    hass.set_state(CoreState.starting)
    await hass.async_block_till_done()

    entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        data={"broker": "test-broker"},
        state=ConfigEntryState.NOT_LOADED,
    )
    entry.add_to_hass(hass)

    # Disable MQTT config entry
    await hass.config_entries.async_set_disabled_by(
        entry.entry_id, ConfigEntryDisabler.USER
    )

    assert entry.state is ConfigEntryState.NOT_LOADED

    # returns False because entry is disabled
    assert not await mqtt.async_wait_for_mqtt_client(hass)

"""Test MQTT utils."""

from collections.abc import Callable
from pathlib import Path
from random import getrandbits
import tempfile
from unittest.mock import patch

import pytest

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.core import CoreState, HomeAssistant

from tests.common import MockConfigEntry
from tests.typing import MqttMockHAClient, MqttMockPahoClient


@pytest.mark.parametrize(
    ("option", "content", "file_created"),
    [
        (mqtt.CONF_CERTIFICATE, "auto", False),
        (mqtt.CONF_CERTIFICATE, "### CA CERTIFICATE ###", True),
        (mqtt.CONF_CLIENT_CERT, "### CLIENT CERTIFICATE ###", True),
        (mqtt.CONF_CLIENT_KEY, "### PRIVATE KEY ###", True),
    ],
)
@pytest.mark.parametrize("temp_dir_prefix", ["create-test"])
async def test_async_create_certificate_temp_files(
    hass: HomeAssistant,
    mock_temp_dir: str,
    option: str,
    content: str,
    file_created: bool,
) -> None:
    """Test creating and reading and recovery certificate files."""
    config = {option: content}
    # Create old file to be able to assert it is removed with auto option
    temp_dir = Path(tempfile.gettempdir()) / mock_temp_dir
    if not temp_dir.exists():
        temp_dir.mkdir(0o700)
    temp_file = temp_dir / option
    with open(temp_file, "wb") as old_file:
        old_file.write(b"old content")
        old_file.close()
    await mqtt.util.async_create_certificate_temp_files(hass, config)
    file_path = mqtt.util.get_file_path(option)
    assert bool(file_path) is file_created
    assert (
        mqtt.util.migrate_certificate_file_to_content(file_path or content) == content
    )

    # Make sure certificate temp files are recovered
    if file_path:
        # Overwrite content of file (except for auto option)
        with open(file_path, "wb") as file:
            file.write(b"invalid")
            file.close()

    await mqtt.util.async_create_certificate_temp_files(hass, config)
    file_path2 = mqtt.util.get_file_path(option)
    assert bool(file_path2) is file_created
    assert (
        mqtt.util.migrate_certificate_file_to_content(file_path2 or content) == content
    )

    assert file_path == file_path2


async def test_reading_non_exitisting_certificate_file() -> None:
    """Test reading a non existing certificate file."""
    assert (
        mqtt.util.migrate_certificate_file_to_content("/home/file_not_exists") is None
    )


@pytest.mark.parametrize("temp_dir_prefix", "unknown")
async def test_return_default_get_file_path(mock_temp_dir: str) -> None:
    """Test get_file_path returns default."""
    with patch(
        "homeassistant.components.mqtt.util.TEMP_DIR_NAME",
        "home-assistant-mqtt-other" + f"-{getrandbits(10):03x}",
    ) as mock_temp_dir:
        tempdir = Path(tempfile.gettempdir()) / mock_temp_dir
        assert not tempdir.exists()
        assert mqtt.util.get_file_path("some_option", "mydefault") == "mydefault"


@patch("homeassistant.components.mqtt.PLATFORMS", [])
async def test_waiting_for_client_not_loaded(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
) -> None:
    """Test waiting for client while mqtt entry is not yet loaded."""
    hass.state = CoreState.starting
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
    hass.async_add_job(_async_just_in_time_subscribe)
    hass.async_add_job(_async_just_in_time_subscribe)
    hass.async_add_job(_async_just_in_time_subscribe)
    hass.async_add_job(_async_just_in_time_subscribe)

    assert entry.state == ConfigEntryState.NOT_LOADED
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert len(unsubs) == 4
    for unsub in unsubs:
        unsub()


@patch("homeassistant.components.mqtt.PLATFORMS", [])
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
    assert entry.state == ConfigEntryState.LOADED

    await _async_just_in_time_subscribe()

    assert unsub is not None
    unsub()


async def test_waiting_for_client_entry_fails(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
) -> None:
    """Test waiting for client where mqtt entry is failing."""
    hass.state = CoreState.starting
    await hass.async_block_till_done()

    entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        data={"broker": "test-broker"},
        state=ConfigEntryState.NOT_LOADED,
    )
    entry.add_to_hass(hass)

    async def _async_just_in_time_subscribe() -> Callable[[], None]:
        assert not await mqtt.async_wait_for_mqtt_client(hass)

    hass.async_add_job(_async_just_in_time_subscribe)
    assert entry.state == ConfigEntryState.NOT_LOADED
    with patch(
        "homeassistant.components.mqtt.async_setup_entry",
        side_effect=Exception,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_waiting_for_client_setup_fails(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
) -> None:
    """Test waiting for client where mqtt entry is failing during setup."""
    hass.state = CoreState.starting
    await hass.async_block_till_done()

    entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        data={"broker": "test-broker"},
        state=ConfigEntryState.NOT_LOADED,
    )
    entry.add_to_hass(hass)

    async def _async_just_in_time_subscribe() -> Callable[[], None]:
        assert not await mqtt.async_wait_for_mqtt_client(hass)

    hass.async_add_job(_async_just_in_time_subscribe)
    assert entry.state == ConfigEntryState.NOT_LOADED

    # Simulate MQTT setup fails before the client would become available
    mqtt_client_mock.connect.side_effect = Exception
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.SETUP_ERROR


@patch("homeassistant.components.mqtt.util.AVAILABILITY_TIMEOUT", 0.01)
async def test_waiting_for_client_timeout(
    hass: HomeAssistant,
) -> None:
    """Test waiting for client with timeout."""
    hass.state = CoreState.starting
    await hass.async_block_till_done()

    entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        data={"broker": "test-broker"},
        state=ConfigEntryState.NOT_LOADED,
    )
    entry.add_to_hass(hass)

    assert entry.state == ConfigEntryState.NOT_LOADED
    # returns False after timeout
    assert not await mqtt.async_wait_for_mqtt_client(hass)


async def test_waiting_for_client_with_disabled_entry(
    hass: HomeAssistant,
) -> None:
    """Test waiting for client with timeout."""
    hass.state = CoreState.starting
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

    assert entry.state == ConfigEntryState.NOT_LOADED

    # returns False because entry is disabled
    assert not await mqtt.async_wait_for_mqtt_client(hass)

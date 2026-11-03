"""Tests for Broadlink remotes."""

import asyncio
from base64 import b64decode, b64encode
from collections.abc import Generator
from datetime import timedelta
from typing import Any
from unittest.mock import call, patch

from broadlink_async.exceptions import (
    BroadlinkException,
    CommandNotSupportedError,
    NetworkTimeoutError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.broadlink.const import DOMAIN
from homeassistant.components.broadlink.remote import CODE_SAVE_DELAY, FLAG_SAVE_DELAY
from homeassistant.components.broadlink.updater import BroadlinkRMUpdateManager
from homeassistant.components.remote import (
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_DELETE_COMMAND,
    SERVICE_LEARN_COMMAND,
    SERVICE_SEND_COMMAND,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import BroadlinkDevice, MockSetup, get_device

REMOTE_DEVICES = ["Entrance", "Living Room", "Office", "Garage", "Study"]

SUBDEVICE = "Living Room"

IR_PACKET = (
    "JgBGAJKVETkRORA6ERQRFBEUERQRFBE5ETkQOhAVEBUQFREUEBUQ"
    "OhEUERQRORE5EBURFBA6EBUQOhE5EBUQFRA6EDoRFBEADQUAAA=="
)
IR_PACKET_ALT = "JgAEAAECAwQ="
RF_PACKET = bytes.fromhex("b2000600111122223333")


@pytest.fixture
def no_learning_delay() -> Generator[None]:
    """Make the learning loop poll the device without waiting."""
    with patch("homeassistant.components.broadlink.remote.LEARNING_POLL_INTERVAL", 0):
        yield


async def _async_setup_remote(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device: BroadlinkDevice,
) -> tuple[MockSetup, str]:
    """Set up a device and return its mocked setup and remote entity id."""
    mock_setup = await device.setup_entry(hass)
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_setup.entry.entry_id
    )
    remote = next(entry for entry in entries if entry.domain == Platform.REMOTE)
    return mock_setup, remote.entity_id


async def _async_reload_remote(hass: HomeAssistant, mock_setup: MockSetup) -> None:
    """Reload the config entry, so the remote reads its codes back from storage."""
    with patch(
        "homeassistant.components.broadlink.device.blk.gendevice",
        return_value=mock_setup.api,
    ):
        await hass.config_entries.async_reload(mock_setup.entry.entry_id)
        await hass.async_block_till_done()


async def _async_call_remote(
    hass: HomeAssistant, service: str, entity_id: str, **data: Any
) -> None:
    """Call a remote action for the subdevice."""
    await hass.services.async_call(
        REMOTE_DOMAIN,
        service,
        {"entity_id": entity_id, "device": SUBDEVICE, **data},
        blocking=True,
    )


async def test_remote_setup_works(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a successful setup with all remotes."""
    for device in map(get_device, REMOTE_DEVICES):
        mock_setup = await device.setup_entry(hass)

        device_entry = device_registry.async_get_device_by_identifier(
            (DOMAIN, mock_setup.entry.unique_id), mock_setup.entry.entry_id
        )
        entries = er.async_entries_for_device(entity_registry, device_entry.id)
        remotes = [entry for entry in entries if entry.domain == Platform.REMOTE]
        assert len(remotes) == 1

        remote = remotes[0]
        assert (
            hass.states.get(remote.entity_id).attributes[ATTR_FRIENDLY_NAME]
            == device.name
        )
        assert hass.states.get(remote.entity_id).state == STATE_ON
        assert mock_setup.api.auth.call_count == 1


async def test_remote_send_command(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sending a command with all remotes."""
    for device in map(get_device, REMOTE_DEVICES):
        mock_setup = await device.setup_entry(hass)

        device_entry = device_registry.async_get_device_by_identifier(
            (DOMAIN, mock_setup.entry.unique_id), mock_setup.entry.entry_id
        )
        entries = er.async_entries_for_device(entity_registry, device_entry.id)
        remotes = [entry for entry in entries if entry.domain == Platform.REMOTE]
        assert len(remotes) == 1

        remote = remotes[0]
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {"entity_id": remote.entity_id, "command": "b64:" + IR_PACKET},
            blocking=True,
        )

        assert mock_setup.api.send_data.call_count == 1
        assert mock_setup.api.send_data.call_args == call(b64decode(IR_PACKET))
        assert mock_setup.api.auth.call_count == 1


@pytest.mark.parametrize(
    ("error", "ticks_to_unavailable"),
    [
        # OSError flips availability on the first failure (fast path).
        (OSError("connection refused"), 1),
        # A generic BroadlinkException keeps the entity available across the
        # first three failed cycles and only flips once SCAN_INTERVAL * 3 has
        # elapsed since the last successful update.
        (BroadlinkException("update failed"), 4),
    ],
)
async def test_remote_availability(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    error: Exception,
    ticks_to_unavailable: int,
) -> None:
    """Test the remote becomes unavailable on disconnect and recovers on reconnect."""
    device = get_device("Garage")
    mock_setup = await device.setup_entry(hass)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_setup.entry.unique_id), mock_setup.entry.entry_id
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    remote = next(entry for entry in entries if entry.domain == Platform.REMOTE)

    assert hass.states.get(remote.entity_id).state == STATE_ON

    mock_setup.api.check_sensors.side_effect = error

    for _ in range(ticks_to_unavailable - 1):
        freezer.tick(BroadlinkRMUpdateManager.SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass.states.get(remote.entity_id).state == STATE_ON

    freezer.tick(BroadlinkRMUpdateManager.SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(remote.entity_id).state == STATE_UNAVAILABLE

    mock_setup.api.check_sensors.side_effect = None

    freezer.tick(BroadlinkRMUpdateManager.SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(remote.entity_id).state == STATE_ON


async def test_remote_turn_off_turn_on(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we do not send commands if the remotes are off."""
    for device in map(get_device, REMOTE_DEVICES):
        mock_setup = await device.setup_entry(hass)

        device_entry = device_registry.async_get_device_by_identifier(
            (DOMAIN, mock_setup.entry.unique_id), mock_setup.entry.entry_id
        )
        entries = er.async_entries_for_device(entity_registry, device_entry.id)
        remotes = [entry for entry in entries if entry.domain == Platform.REMOTE]
        assert len(remotes) == 1

        remote = remotes[0]
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_TURN_OFF,
            {"entity_id": remote.entity_id},
            blocking=True,
        )
        assert hass.states.get(remote.entity_id).state == STATE_OFF

        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {"entity_id": remote.entity_id, "command": "b64:" + IR_PACKET},
            blocking=True,
        )
        assert mock_setup.api.send_data.call_count == 0

        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": remote.entity_id},
            blocking=True,
        )
        assert hass.states.get(remote.entity_id).state == STATE_ON

        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {"entity_id": remote.entity_id, "command": "b64:" + IR_PACKET},
            blocking=True,
        )
        assert mock_setup.api.send_data.call_count == 1
        assert mock_setup.api.send_data.call_args == call(b64decode(IR_PACKET))
        assert mock_setup.api.auth.call_count == 1


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(BroadlinkException("boom"), id="broadlink_error"),
        pytest.param(OSError("boom"), id="os_error"),
    ],
)
async def test_remote_send_command_error_stops_sending(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    error: Exception,
) -> None:
    """Test a failure aborts the remaining commands and raises."""
    device = get_device("Entrance")
    mock_setup, entity_id = await _async_setup_remote(hass, entity_registry, device)
    mock_setup.api.send_data.side_effect = [None, error]

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {
                "entity_id": entity_id,
                "command": ["b64:" + IR_PACKET] * 3,
                "delay_secs": 0,
            },
            blocking=True,
        )

    assert mock_setup.api.send_data.call_count == 2
    assert exc_info.value.translation_key == "send_command_failed"
    assert exc_info.value.translation_domain == DOMAIN


@pytest.mark.usefixtures("no_learning_delay")
async def test_remote_send_command_error_stores_toggle_flags(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the toggle flags are stored when sending fails partway."""
    device = get_device("Entrance")
    mock_setup, entity_id = await _async_setup_remote(hass, entity_registry, device)
    mock_setup.api.check_data.side_effect = [
        b64decode(IR_PACKET),
        b64decode(IR_PACKET_ALT),
    ]
    await _async_call_remote(
        hass, SERVICE_LEARN_COMMAND, entity_id, command=["toggle"], alternative=True
    )
    mock_setup.api.send_data.side_effect = [None, BroadlinkException("boom")]

    with pytest.raises(HomeAssistantError):
        await _async_call_remote(
            hass,
            SERVICE_SEND_COMMAND,
            entity_id,
            command=["toggle", "toggle"],
            delay_secs=0,
        )

    freezer.tick(timedelta(seconds=FLAG_SAVE_DELAY))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await _async_reload_remote(hass, mock_setup)
    mock_setup.api.send_data.reset_mock(side_effect=True)

    await _async_call_remote(hass, SERVICE_SEND_COMMAND, entity_id, command=["toggle"])

    assert mock_setup.api.send_data.call_args_list == [call(b64decode(IR_PACKET_ALT))]


@pytest.mark.usefixtures("no_learning_delay")
async def test_remote_learn_command_error_stops_learning(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a fatal learning error stops learning but stores what was learned."""
    device = get_device("Entrance")
    mock_setup, entity_id = await _async_setup_remote(hass, entity_registry, device)
    mock_setup.api.check_data.return_value = b64decode(IR_PACKET)
    mock_setup.api.enter_learning.side_effect = [None, NetworkTimeoutError("boom")]

    with pytest.raises(HomeAssistantError) as exc_info:
        await _async_call_remote(
            hass,
            SERVICE_LEARN_COMMAND,
            entity_id,
            command=["first", "second", "third"],
        )

    assert mock_setup.api.enter_learning.call_count == 2
    assert exc_info.value.translation_key == "learn_command_failed"
    assert exc_info.value.translation_domain == DOMAIN

    await _async_reload_remote(hass, mock_setup)
    await _async_call_remote(hass, SERVICE_SEND_COMMAND, entity_id, command=["first"])

    assert mock_setup.api.send_data.call_args_list == [call(b64decode(IR_PACKET))]


@pytest.mark.parametrize(
    ("side_effect", "translation_key", "learned"),
    [
        pytest.param(
            [None, BroadlinkException("boom"), None],
            "learn_command_failed",
            ["first", "third"],
            id="one_command_failed",
        ),
        pytest.param(
            [BroadlinkException("boom"), None, BroadlinkException("boom")],
            "learn_commands_failed",
            ["second"],
            id="two_commands_failed",
        ),
    ],
)
@pytest.mark.usefixtures("no_learning_delay")
async def test_remote_learn_command_skips_failed_commands(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    side_effect: list[Exception | None],
    translation_key: str,
    learned: list[str],
) -> None:
    """Test an unreadable command is skipped while the others are learned."""
    device = get_device("Entrance")
    mock_setup, entity_id = await _async_setup_remote(hass, entity_registry, device)
    mock_setup.api.check_data.return_value = b64decode(IR_PACKET)
    mock_setup.api.enter_learning.side_effect = side_effect

    with pytest.raises(HomeAssistantError) as exc_info:
        await _async_call_remote(
            hass,
            SERVICE_LEARN_COMMAND,
            entity_id,
            command=["first", "second", "third"],
        )

    assert mock_setup.api.enter_learning.call_count == 3
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_domain == DOMAIN

    await _async_call_remote(
        hass, SERVICE_SEND_COMMAND, entity_id, command=learned, delay_secs=0
    )

    assert mock_setup.api.send_data.call_args_list == [
        call(b64decode(IR_PACKET))
    ] * len(learned)


@pytest.mark.usefixtures("no_learning_delay")
async def test_remote_delete_command_reports_unknown_commands(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test partially unknown commands are reported, known ones are deleted."""
    device = get_device("Entrance")
    mock_setup, entity_id = await _async_setup_remote(hass, entity_registry, device)
    mock_setup.api.check_data.return_value = b64decode(IR_PACKET)
    await _async_call_remote(
        hass, SERVICE_LEARN_COMMAND, entity_id, command=["known", "other"]
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await _async_call_remote(
            hass, SERVICE_DELETE_COMMAND, entity_id, command=["known", "unknown"]
        )

    assert exc_info.value.translation_key == "command_not_found"
    assert exc_info.value.translation_domain == DOMAIN

    freezer.tick(timedelta(seconds=CODE_SAVE_DELAY))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await _async_reload_remote(hass, mock_setup)

    await _async_call_remote(hass, SERVICE_SEND_COMMAND, entity_id, command=["other"])
    assert mock_setup.api.send_data.call_args_list == [call(b64decode(IR_PACKET))]

    with pytest.raises(ServiceValidationError, match="Command not found: 'known'"):
        await _async_call_remote(
            hass, SERVICE_SEND_COMMAND, entity_id, command=["known"]
        )


@pytest.mark.parametrize(
    ("commands", "subdevice", "translation_key"),
    [
        pytest.param(
            ["unknown", "missing"],
            SUBDEVICE,
            "commands_not_found",
            id="only_unknown_commands",
        ),
        pytest.param(
            ["known"],
            "Nonexistent",
            "device_not_found",
            id="unknown_subdevice",
        ),
    ],
)
@pytest.mark.usefixtures("no_learning_delay")
async def test_remote_delete_command_reports_invalid_input(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    commands: list[str],
    subdevice: str,
    translation_key: str,
) -> None:
    """Test nothing is deleted when no command matches the request."""
    device = get_device("Entrance")
    mock_setup, entity_id = await _async_setup_remote(hass, entity_registry, device)
    mock_setup.api.check_data.return_value = b64decode(IR_PACKET)
    await _async_call_remote(
        hass, SERVICE_LEARN_COMMAND, entity_id, command=["known", "other"]
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_DELETE_COMMAND,
            {"entity_id": entity_id, "device": subdevice, "command": commands},
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_domain == DOMAIN

    await _async_call_remote(
        hass, SERVICE_SEND_COMMAND, entity_id, command=["known", "other"], delay_secs=0
    )

    assert mock_setup.api.send_data.call_args_list == [call(b64decode(IR_PACKET))] * 2


@pytest.fixture
def mock_sleep() -> Generator[None]:
    """Skip the one-second delays while learning RF codes."""
    with patch("homeassistant.components.broadlink.remote.asyncio.sleep"):
        yield


@pytest.mark.usefixtures("mock_sleep")
async def test_remote_learn_rf_command(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test learning an RF command uses the swept frequency and stores the code."""
    device = get_device("Garage")
    mock_setup, entity_id = await _async_setup_remote(hass, entity_registry, device)
    mock_setup.api.check_frequency.return_value = (True, 433.92)
    mock_setup.api.check_data.return_value = RF_PACKET

    await _async_call_remote(
        hass, SERVICE_LEARN_COMMAND, entity_id, command="light", command_type="rf"
    )

    assert mock_setup.api.sweep_frequency.call_count == 1
    assert mock_setup.api.find_rf_packet.call_args == call(433.92)
    codes = hass_storage[f"broadlink_remote_{device.mac}_codes"]["data"]
    assert codes == {SUBDEVICE: {"light": b64encode(RF_PACKET).decode()}}

    await _async_call_remote(hass, SERVICE_SEND_COMMAND, entity_id, command="light")

    assert mock_setup.api.send_data.call_args == call(RF_PACKET)


@pytest.mark.parametrize(
    (
        "api_method",
        "side_effect",
        "frequency_result",
        "learning_timeout",
        "sweep_cancels",
    ),
    [
        pytest.param(
            "sweep_frequency",
            CommandNotSupportedError(-4, "Command not supported"),
            (True, 433.92),
            timedelta(seconds=30),
            0,
            id="sweep_not_supported",
        ),
        pytest.param(
            "check_frequency",
            CommandNotSupportedError(-4, "Command not supported"),
            (True, 433.92),
            timedelta(seconds=30),
            1,
            id="check_frequency_error",
        ),
        pytest.param(
            "check_frequency",
            None,
            (False, 0.0),
            # Short enough for the test, long enough to poll at least once.
            timedelta(milliseconds=10),
            1,
            id="frequency_never_locks",
        ),
        pytest.param(
            "find_rf_packet",
            CommandNotSupportedError(-4, "Command not supported"),
            (True, 433.92),
            timedelta(seconds=30),
            0,
            id="find_packet_not_supported",
        ),
    ],
)
@pytest.mark.usefixtures("mock_sleep")
async def test_remote_learn_rf_command_failure(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
    api_method: str,
    side_effect: Exception | None,
    frequency_result: tuple[bool, float],
    learning_timeout: timedelta,
    sweep_cancels: int,
) -> None:
    """Test a failure while learning an RF command is reported to the caller."""
    device = get_device("Garage")
    mock_setup, entity_id = await _async_setup_remote(hass, entity_registry, device)
    mock_setup.api.check_frequency.return_value = frequency_result
    getattr(mock_setup.api, api_method).side_effect = side_effect

    with (
        patch(
            "homeassistant.components.broadlink.remote.LEARNING_TIMEOUT",
            learning_timeout,
        ),
        pytest.raises(HomeAssistantError, match="Failed to learn command 'light'"),
    ):
        await _async_call_remote(
            hass, SERVICE_LEARN_COMMAND, entity_id, command="light", command_type="rf"
        )

    assert getattr(mock_setup.api, api_method).called
    assert mock_setup.api.cancel_sweep_frequency.call_count == sweep_cancels
    assert f"broadlink_remote_{device.mac}_codes" not in hass_storage


@pytest.mark.usefixtures("mock_sleep")
async def test_remote_learn_rf_command_cancelled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test cancelling RF learning while polling the frequency ends the sweep."""
    device = get_device("Garage")
    mock_setup, entity_id = await _async_setup_remote(hass, entity_registry, device)
    mock_setup.api.check_frequency.side_effect = asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await _async_call_remote(
            hass, SERVICE_LEARN_COMMAND, entity_id, command="light", command_type="rf"
        )

    assert mock_setup.api.cancel_sweep_frequency.call_count == 1


@pytest.mark.parametrize(
    ("service", "service_data"),
    [
        pytest.param(
            SERVICE_SEND_COMMAND,
            {"command": "b64:" + b64encode(RF_PACKET).decode()},
            id="send",
        ),
        pytest.param(
            SERVICE_SEND_COMMAND,
            {"command": "b64:" + b64encode(b"\xb1" + RF_PACKET[1:]).decode()},
            id="send_rm4_packet",
        ),
        pytest.param(
            SERVICE_SEND_COMMAND,
            {"command": "b64:" + b64encode(b"\xb4" + RF_PACKET[1:]).decode()},
            id="send_315mhz_packet",
        ),
        pytest.param(
            SERVICE_LEARN_COMMAND,
            {"device": "fan", "command": "light", "command_type": "rf"},
            id="learn",
        ),
    ],
)
async def test_remote_rf_not_supported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    service: str,
    service_data: dict[str, Any],
) -> None:
    """Test RF actions on a model without RF raise a validation error."""
    device = get_device("Entrance")
    mock_setup, entity_id = await _async_setup_remote(hass, entity_registry, device)
    del mock_setup.api.sweep_frequency

    with pytest.raises(ServiceValidationError, match="doesn't support RF commands"):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            service,
            {"entity_id": entity_id, **service_data},
            blocking=True,
        )

    assert mock_setup.api.send_data.call_count == 0

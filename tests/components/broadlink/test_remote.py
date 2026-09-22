"""Tests for Broadlink remotes."""

from base64 import b64decode
from datetime import timedelta
from typing import Any
from unittest.mock import call, patch

from broadlink.exceptions import BroadlinkException, NetworkTimeoutError
from freezegun.api import FrozenDateTimeFactory
import pytest

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

from tests.common import async_fire_time_changed

REMOTE_DEVICES = ["Entrance", "Living Room", "Office", "Garage"]

SUBDEVICE = "Living Room"

IR_PACKET = (
    "JgBGAJKVETkRORA6ERQRFBEUERQRFBE5ETkQOhAVEBUQFREUEBUQ"
    "OhEUERQRORE5EBURFBA6EBUQOhE5EBUQFRA6EDoRFBEADQUAAA=="
)


def _codes_storage_key(device: BroadlinkDevice) -> str:
    """Return the storage key holding the codes of a device."""
    return f"broadlink_remote_{device.mac}_codes"


def _flags_storage_key(device: BroadlinkDevice) -> str:
    """Return the storage key holding the toggle flags of a device."""
    return f"broadlink_remote_{device.mac}_flags"


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


async def test_remote_send_command_error_stores_toggle_flags(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the toggle flags are stored when sending fails partway."""
    device = get_device("Entrance")
    hass_storage[_codes_storage_key(device)] = {
        "version": 1,
        "data": {SUBDEVICE: {"toggle": [IR_PACKET, IR_PACKET]}},
    }
    mock_setup, entity_id = await _async_setup_remote(hass, entity_registry, device)
    mock_setup.api.send_data.side_effect = [None, BroadlinkException("boom")]

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {
                "entity_id": entity_id,
                "device": SUBDEVICE,
                "command": ["toggle", "toggle"],
                "delay_secs": 0,
            },
            blocking=True,
        )

    freezer.tick(timedelta(seconds=FLAG_SAVE_DELAY))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass_storage[_flags_storage_key(device)]["data"] == {SUBDEVICE: 1}


async def test_remote_learn_command_error_stops_learning(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a fatal learning error stops learning but stores what was learned."""
    device = get_device("Entrance")
    mock_setup, entity_id = await _async_setup_remote(hass, entity_registry, device)
    mock_setup.api.check_data.return_value = b64decode(IR_PACKET)
    mock_setup.api.enter_learning.side_effect = [None, NetworkTimeoutError("boom")]

    with (
        patch("homeassistant.components.broadlink.remote.asyncio.sleep"),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_LEARN_COMMAND,
            {
                "entity_id": entity_id,
                "device": SUBDEVICE,
                "command": ["first", "second", "third"],
            },
            blocking=True,
        )

    assert mock_setup.api.enter_learning.call_count == 2
    assert exc_info.value.translation_key == "learn_command_failed"
    assert exc_info.value.translation_domain == DOMAIN
    assert hass_storage[_codes_storage_key(device)]["data"] == {
        SUBDEVICE: {"first": IR_PACKET}
    }


@pytest.mark.parametrize(
    ("side_effect", "translation_key", "learned"),
    [
        pytest.param(
            [None, BroadlinkException("boom"), None],
            "learn_command_failed",
            {"first": IR_PACKET, "third": IR_PACKET},
            id="one_command_failed",
        ),
        pytest.param(
            [BroadlinkException("boom"), None, BroadlinkException("boom")],
            "learn_commands_failed",
            {"second": IR_PACKET},
            id="two_commands_failed",
        ),
    ],
)
async def test_remote_learn_command_skips_failed_commands(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    entity_registry: er.EntityRegistry,
    side_effect: list[Exception | None],
    translation_key: str,
    learned: dict[str, str],
) -> None:
    """Test an unreadable command is skipped while the others are learned."""
    device = get_device("Entrance")
    mock_setup, entity_id = await _async_setup_remote(hass, entity_registry, device)
    mock_setup.api.check_data.return_value = b64decode(IR_PACKET)
    mock_setup.api.enter_learning.side_effect = side_effect

    with (
        patch("homeassistant.components.broadlink.remote.asyncio.sleep"),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_LEARN_COMMAND,
            {
                "entity_id": entity_id,
                "device": SUBDEVICE,
                "command": ["first", "second", "third"],
            },
            blocking=True,
        )

    assert mock_setup.api.enter_learning.call_count == 3
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_domain == DOMAIN
    assert hass_storage[_codes_storage_key(device)]["data"] == {SUBDEVICE: learned}


async def test_remote_delete_command_reports_unknown_commands(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test partially unknown commands are reported, known ones are deleted."""
    device = get_device("Entrance")
    hass_storage[_codes_storage_key(device)] = {
        "version": 1,
        "data": {SUBDEVICE: {"known": IR_PACKET, "other": IR_PACKET}},
    }
    _, entity_id = await _async_setup_remote(hass, entity_registry, device)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_DELETE_COMMAND,
            {
                "entity_id": entity_id,
                "device": SUBDEVICE,
                "command": ["known", "unknown"],
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "command_not_found"
    assert exc_info.value.translation_domain == DOMAIN

    freezer.tick(timedelta(seconds=CODE_SAVE_DELAY))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass_storage[_codes_storage_key(device)]["data"] == {
        SUBDEVICE: {"other": IR_PACKET}
    }


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
async def test_remote_delete_command_reports_invalid_input(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    commands: list[str],
    subdevice: str,
    translation_key: str,
) -> None:
    """Test nothing is deleted when no command matches the request."""
    device = get_device("Entrance")
    codes = {SUBDEVICE: {"known": IR_PACKET, "other": IR_PACKET}}
    hass_storage[_codes_storage_key(device)] = {"version": 1, "data": codes}
    _, entity_id = await _async_setup_remote(hass, entity_registry, device)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_DELETE_COMMAND,
            {"entity_id": entity_id, "device": subdevice, "command": commands},
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_domain == DOMAIN

    freezer.tick(timedelta(seconds=CODE_SAVE_DELAY))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass_storage[_codes_storage_key(device)]["data"] == codes

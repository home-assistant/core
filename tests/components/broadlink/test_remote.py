"""Tests for Broadlink remotes."""

from base64 import b64decode, b64encode
from datetime import timedelta
from typing import Any
from unittest.mock import call, patch

from broadlink.exceptions import BroadlinkException, CommandNotSupportedError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.broadlink.const import DOMAIN
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

from . import get_device

from tests.common import async_fire_time_changed

REMOTE_DEVICES = ["Entrance", "Living Room", "Office", "Garage", "Study"]

IR_PACKET = (
    "JgBGAJKVETkRORA6ERQRFBEUERQRFBE5ETkQOhAVEBUQFREUEBUQ"
    "OhEUERQRORE5EBURFBA6EBUQOhE5EBUQFRA6EDoRFBEADQUAAA=="
)
RF_PACKET = bytes.fromhex("b2000600111122223333")


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


@pytest.fixture
def mock_sleep():
    """Skip the one-second polling delays while learning codes."""
    with patch("homeassistant.components.broadlink.remote.asyncio.sleep"):
        yield


def _get_remote_entity_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    entry_unique_id: str,
    entry_id: str,
) -> str:
    """Return the remote entity id of a set up device."""
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry_unique_id), entry_id
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    return next(e.entity_id for e in entries if e.domain == Platform.REMOTE)


@pytest.mark.usefixtures("mock_sleep")
async def test_remote_learn_rf_command(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test learning an RF command uses the swept frequency and stores the code."""
    device = get_device("Garage")
    mock_api = device.get_mock_api()
    mock_api.check_frequency.return_value = (True, 433.92)
    mock_api.check_data.return_value = RF_PACKET
    mock_setup = await device.setup_entry(hass, mock_api=mock_api)
    entity_id = _get_remote_entity_id(
        hass,
        device_registry,
        entity_registry,
        mock_setup.entry.unique_id,
        mock_setup.entry.entry_id,
    )

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_LEARN_COMMAND,
        {
            "entity_id": entity_id,
            "device": "fan",
            "command": "light",
            "command_type": "rf",
        },
        blocking=True,
    )

    assert mock_api.sweep_frequency.call_count == 1
    assert mock_api.find_rf_packet.call_args == call(433.92)
    codes = hass_storage[f"broadlink_remote_{device.mac}_codes"]["data"]
    assert codes == {"fan": {"light": b64encode(RF_PACKET).decode()}}

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {"entity_id": entity_id, "device": "fan", "command": "light"},
        blocking=True,
    )
    assert mock_api.send_data.call_args == call(RF_PACKET)


@pytest.mark.usefixtures("mock_sleep")
async def test_remote_learn_rf_command_realigns_packet(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test an RM4 Pro RF capture shifted by one duration is stored realigned."""
    misaligned = bytes.fromhex("b1c01600b09e0600350d00019a280c0d280d00019a280c0d280d")
    aligned = bytes.fromhex("b1c01500b09e06000d00019a280c0d280d00019a280c0d280d")
    device = get_device("Garage")
    mock_api = device.get_mock_api()
    mock_api.check_frequency.return_value = (True, 433.84)
    mock_api.check_data.return_value = misaligned
    mock_setup = await device.setup_entry(hass, mock_api=mock_api)
    entity_id = _get_remote_entity_id(
        hass,
        device_registry,
        entity_registry,
        mock_setup.entry.unique_id,
        mock_setup.entry.entry_id,
    )

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_LEARN_COMMAND,
        {
            "entity_id": entity_id,
            "device": "patio_heater",
            "command": "power",
            "command_type": "rf",
        },
        blocking=True,
    )

    codes = hass_storage[f"broadlink_remote_{device.mac}_codes"]["data"]
    assert codes == {"patio_heater": {"power": b64encode(aligned).decode()}}


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
    device_registry: dr.DeviceRegistry,
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
    mock_api = device.get_mock_api()
    mock_api.check_frequency.return_value = frequency_result
    getattr(mock_api, api_method).side_effect = side_effect
    mock_setup = await device.setup_entry(hass, mock_api=mock_api)
    entity_id = _get_remote_entity_id(
        hass,
        device_registry,
        entity_registry,
        mock_setup.entry.unique_id,
        mock_setup.entry.entry_id,
    )

    with (
        patch(
            "homeassistant.components.broadlink.remote.LEARNING_TIMEOUT",
            learning_timeout,
        ),
        pytest.raises(HomeAssistantError, match="Failed to learn command light"),
    ):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_LEARN_COMMAND,
            {
                "entity_id": entity_id,
                "device": "fan",
                "command": "light",
                "command_type": "rf",
            },
            blocking=True,
        )

    assert getattr(mock_api, api_method).called
    assert mock_api.cancel_sweep_frequency.call_count == sweep_cancels
    assert f"broadlink_remote_{device.mac}_codes" not in hass_storage


@pytest.mark.usefixtures("mock_sleep")
async def test_remote_learn_ir_command_partial_failure(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test commands learned before a failure are kept and the failure is raised."""
    device = get_device("Entrance")
    mock_api = device.get_mock_api()
    mock_api.enter_learning.side_effect = [
        None,
        BroadlinkException("Learning failed"),
    ]
    mock_api.check_data.return_value = b64decode(IR_PACKET)
    mock_setup = await device.setup_entry(hass, mock_api=mock_api)
    entity_id = _get_remote_entity_id(
        hass,
        device_registry,
        entity_registry,
        mock_setup.entry.unique_id,
        mock_setup.entry.entry_id,
    )

    with pytest.raises(HomeAssistantError, match="Failed to learn command off"):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_LEARN_COMMAND,
            {"entity_id": entity_id, "device": "tv", "command": ["on", "off"]},
            blocking=True,
        )

    codes = hass_storage[f"broadlink_remote_{device.mac}_codes"]["data"]
    assert codes == {"tv": {"on": IR_PACKET}}


async def test_remote_send_unknown_command(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sending a command that was never learned raises a validation error."""
    device = get_device("Garage")
    mock_setup = await device.setup_entry(hass)
    entity_id = _get_remote_entity_id(
        hass,
        device_registry,
        entity_registry,
        mock_setup.entry.unique_id,
        mock_setup.entry.entry_id,
    )

    with pytest.raises(ServiceValidationError, match="Command not found: 'light'"):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {"entity_id": entity_id, "device": "fan", "command": "light"},
            blocking=True,
        )

    assert mock_setup.api.send_data.call_count == 0


async def test_remote_send_command_failure(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a device error while sending is reported to the caller."""
    device = get_device("Entrance")
    mock_api = device.get_mock_api()
    mock_api.send_data.side_effect = BroadlinkException("Send failed")
    mock_setup = await device.setup_entry(hass, mock_api=mock_api)
    entity_id = _get_remote_entity_id(
        hass,
        device_registry,
        entity_registry,
        mock_setup.entry.unique_id,
        mock_setup.entry.entry_id,
    )

    with pytest.raises(HomeAssistantError, match="Failed to send command"):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {"entity_id": entity_id, "command": "b64:" + IR_PACKET},
            blocking=True,
        )


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
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    service: str,
    service_data: dict[str, Any],
) -> None:
    """Test RF actions on a model without RF raise a validation error."""
    device = get_device("Entrance")
    mock_api = device.get_mock_api()
    del mock_api.sweep_frequency
    mock_setup = await device.setup_entry(hass, mock_api=mock_api)
    entity_id = _get_remote_entity_id(
        hass,
        device_registry,
        entity_registry,
        mock_setup.entry.unique_id,
        mock_setup.entry.entry_id,
    )

    with pytest.raises(ServiceValidationError, match="doesn't support RF commands"):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            service,
            {"entity_id": entity_id, **service_data},
            blocking=True,
        )

    assert mock_api.send_data.call_count == 0


@pytest.mark.parametrize(
    ("service_data", "message"),
    [
        pytest.param(
            {"device": "fan", "command": "on"},
            "Device not found: fan",
            id="unknown_device",
        ),
        pytest.param(
            {"device": "tv", "command": "off"},
            "Command not found: off",
            id="unknown_command",
        ),
        pytest.param(
            {"device": "tv", "command": ["off", "mute"]},
            "Commands not found: off, mute",
            id="unknown_commands",
        ),
    ],
)
async def test_remote_delete_command_not_found(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
    service_data: dict[str, Any],
    message: str,
) -> None:
    """Test deleting a device or commands that were never learned raises."""
    device = get_device("Entrance")
    hass_storage[f"broadlink_remote_{device.mac}_codes"] = {
        "version": 1,
        "data": {"tv": {"on": IR_PACKET}},
    }
    mock_setup = await device.setup_entry(hass)
    entity_id = _get_remote_entity_id(
        hass,
        device_registry,
        entity_registry,
        mock_setup.entry.unique_id,
        mock_setup.entry.entry_id,
    )

    with pytest.raises(ServiceValidationError, match=message):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_DELETE_COMMAND,
            {"entity_id": entity_id, **service_data},
            blocking=True,
        )

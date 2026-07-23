"""Tests for the Honeywell Lyric binary sensor platform."""

from unittest.mock import MagicMock

from aiolyric.objects.device import LyricDevice
from aiolyric.objects.priority import LyricRoom
import pytest

from homeassistant.components.lyric.binary_sensor import (
    ACCESSORY_BINARY_SENSORS,
    DEVICE_BINARY_SENSORS,
    async_setup_entry,
)
from homeassistant.const import EntityCategory

MAC_ID = "5CFCE1B67035"


def _mock_accessory(
    accessory_id: int, accessory_type: str, detect_motion: bool = False
) -> MagicMock:
    accessory = MagicMock()
    accessory.id = accessory_id
    accessory.type = accessory_type
    accessory.detect_motion = detect_motion
    return accessory


def _mock_device(
    mac_id: str = "AABBCC",
    vacation_enabled: bool = False,
    pairing_enabled: bool = True,
) -> MagicMock:
    device = MagicMock()
    device.mac_id = mac_id
    device.vacation_hold.enabled = vacation_enabled
    device.settings.device_pairing_enabled = pairing_enabled
    return device


def _coordinator_for(
    device: LyricDevice, rooms: list[LyricRoom] | None = None
) -> MagicMock:
    """Build a coordinator mock that supports full entity property resolution.

    Wires up locations_dict/rooms_dict so LyricDeviceEntity.device and
    LyricAccessoryEntity.room/.accessory resolve through the same lookups
    the real entities use, not just a flat pre-set attribute.
    """
    location = MagicMock()
    location.location_id = "location1"
    location.devices = [device]
    location.devices_dict = {device.mac_id: device}

    coordinator = MagicMock()
    coordinator.data.locations = [location]
    coordinator.data.locations_dict = {"location1": location}
    coordinator.data.rooms_dict = {
        device.mac_id: {room.id: room for room in rooms or []}
    }
    return coordinator


async def _setup_and_collect(coordinator: MagicMock) -> tuple[list, list]:
    """Run async_setup_entry and return (device_entities, accessory_entities)."""
    entry = MagicMock()
    entry.runtime_data = coordinator

    added: list[list] = []
    async_add_entities = MagicMock(
        side_effect=lambda entities: added.append(list(entities))
    )

    await async_setup_entry(MagicMock(), entry, async_add_entities)
    return added[0], added[1]


async def test_async_setup_entry_generates_correct_unique_ids() -> None:
    """Entity unique_ids are correctly formed and don't collide across rooms.

    Uses real LyricDevice/LyricRoom/LyricAccessory objects (constructed with
    field names aiolyric 2.1.1 already parses correctly) to verify the ID
    formula itself: device-level IDs key off the device MAC, accessory-level
    IDs additionally key off room id and accessory id - the parts most
    likely to collide when more room/accessory sensors are added later.
    """
    device = LyricDevice(
        MagicMock(),
        {
            "macID": MAC_ID,
            "vacationHold": {"enabled": False},
            "settings": {"devicePairingEnabled": True},
        },
    )
    room1 = LyricRoom(
        {
            "id": 1,
            "accessories": [
                {"id": 1, "type": "IndoorAirSensor", "detectMotion": False},
                {"id": 0, "type": "Thermostat", "detectMotion": False},
            ],
        }
    )
    room2 = LyricRoom(
        {
            "id": 2,
            "accessories": [
                {"id": 2, "type": "IndoorAirSensor", "detectMotion": True},
            ],
        }
    )

    coordinator = _coordinator_for(device, [room1, room2])
    device_entities, accessory_entities = await _setup_and_collect(coordinator)

    assert {e.unique_id for e in device_entities} == {
        f"{MAC_ID}_vacation_hold",
        f"{MAC_ID}_device_pairing_enabled",
    }

    # Only the IndoorAirSensor accessories produce Room Motion entities, one
    # per room, and each unique_id is distinct despite sharing a device MAC.
    assert {e.unique_id for e in accessory_entities} == {
        f"{MAC_ID}_room1_acc1_room_motion",
        f"{MAC_ID}_room2_acc2_room_motion",
    }


async def test_device_pairing_enabled_end_to_end_with_real_payload() -> None:
    """Device Pairing Enabled resolves correctly through real object parsing.

    Unlike vacation_hold and room_motion, this field isn't affected by any
    known aiolyric field-name mismatch, so this exercises the full
    integration boundary (real LyricDevice -> entity.is_on) end-to-end.
    """
    device = LyricDevice(
        MagicMock(),
        {
            "macID": MAC_ID,
            "vacationHold": {"Enabled": False},
            "settings": {"devicePairingEnabled": True},
        },
    )
    coordinator = _coordinator_for(device)
    device_entities, _ = await _setup_and_collect(coordinator)

    pairing_entity = next(
        e
        for e in device_entities
        if e.entity_description.key == "device_pairing_enabled"
    )
    assert pairing_entity.unique_id == f"{MAC_ID}_device_pairing_enabled"
    assert pairing_entity.is_on is True


@pytest.mark.xfail(
    strict=True,
    reason=(
        "aiolyric 2.1.1's VacationHold.enabled reads JSON key 'enabled', but "
        "Resideo's live API returns 'Enabled' (capital E). Fixed upstream in "
        "clutch2sft/aiolyric#fix-vacation-hold-key; once that's released and "
        "the manifest pin is bumped, this will start passing for real and "
        "this marker must be removed."
    ),
)
async def test_vacation_hold_end_to_end_with_live_payload() -> None:
    """Vacation Hold should resolve True given a live-shaped payload.

    Built from the actual API response shape captured from a live account,
    not a synthetic/pre-parsed mock - currently fails because of the
    pending key-name fix, by design.
    """
    device = LyricDevice(
        MagicMock(),
        {
            "macID": MAC_ID,
            "vacationHold": {"Enabled": True},
            "settings": {"devicePairingEnabled": True},
        },
    )
    coordinator = _coordinator_for(device)
    device_entities, _ = await _setup_and_collect(coordinator)

    vacation_entity = next(
        e for e in device_entities if e.entity_description.key == "vacation_hold"
    )
    assert vacation_entity.is_on is True


@pytest.mark.xfail(
    strict=True,
    reason=(
        "aiolyric 2.1.1's LyricAccessory.type reads JSON key 'type', but "
        "Resideo's live API returns 'sensorType'. Fixed upstream in "
        "timmo001/aiolyric#165; once that's released and the manifest pin is "
        "bumped, this will start passing for real and this marker must be "
        "removed."
    ),
)
async def test_room_motion_end_to_end_with_live_payload() -> None:
    """Room Motion should be created and reflect real data from a live payload.

    Built from the actual /priority response shape captured from a live
    T9-T10 account - currently fails because accessory.type never matches
    "IndoorAirSensor" under the pending key-name fix, so no entity is
    created at all.
    """
    device = LyricDevice(MagicMock(), {"macID": MAC_ID})
    room = LyricRoom(
        {
            "id": 1,
            "accessories": [
                {"id": 1, "sensorType": "IndoorAirSensor", "detectMotion": True},
            ],
        }
    )
    coordinator = _coordinator_for(device, [room])
    _, accessory_entities = await _setup_and_collect(coordinator)

    motion_entity = next(
        e for e in accessory_entities if e.entity_description.key == "room_motion"
    )
    assert motion_entity.unique_id == f"{MAC_ID}_room1_acc1_room_motion"
    assert motion_entity.is_on is True


def test_vacation_hold_value_fn() -> None:
    """Vacation Hold reflects device.vacation_hold.enabled."""
    description = next(d for d in DEVICE_BINARY_SENSORS if d.key == "vacation_hold")
    assert description.value_fn(_mock_device(vacation_enabled=True)) is True
    assert description.value_fn(_mock_device(vacation_enabled=False)) is False


def test_device_pairing_enabled_value_fn() -> None:
    """Device Pairing Enabled reflects device.settings.device_pairing_enabled."""
    description = next(
        d for d in DEVICE_BINARY_SENSORS if d.key == "device_pairing_enabled"
    )
    assert description.value_fn(_mock_device(pairing_enabled=True)) is True
    assert description.value_fn(_mock_device(pairing_enabled=False)) is False


def test_device_pairing_enabled_is_diagnostic() -> None:
    """Device Pairing Enabled is diagnostic; Vacation Hold is not."""
    pairing = next(
        d for d in DEVICE_BINARY_SENSORS if d.key == "device_pairing_enabled"
    )
    vacation = next(d for d in DEVICE_BINARY_SENSORS if d.key == "vacation_hold")
    assert pairing.entity_category is EntityCategory.DIAGNOSTIC
    assert vacation.entity_category is None


def test_room_motion_suitable_fn_filters_by_accessory_type() -> None:
    """Room Motion only applies to IndoorAirSensor accessories."""
    description = ACCESSORY_BINARY_SENSORS[0]
    sensor_accessory = _mock_accessory(1, "IndoorAirSensor")
    thermostat_accessory = _mock_accessory(0, "Thermostat")
    assert description.suitable_fn(None, sensor_accessory) is True
    assert description.suitable_fn(None, thermostat_accessory) is False


def test_room_motion_value_fn() -> None:
    """Room Motion reflects accessory.detect_motion."""
    description = ACCESSORY_BINARY_SENSORS[0]
    motion_detected = _mock_accessory(1, "IndoorAirSensor", detect_motion=True)
    no_motion = _mock_accessory(1, "IndoorAirSensor", detect_motion=False)
    assert description.value_fn(None, motion_detected) is True
    assert description.value_fn(None, no_motion) is False

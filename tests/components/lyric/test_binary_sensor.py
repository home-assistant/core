"""Tests for the Honeywell Lyric binary sensor platform."""

from unittest.mock import MagicMock

from homeassistant.components.lyric.binary_sensor import (
    ACCESSORY_BINARY_SENSORS,
    DEVICE_BINARY_SENSORS,
    async_setup_entry,
)
from homeassistant.const import EntityCategory


def _mock_accessory(
    accessory_id: int, accessory_type: str, detect_motion: bool = False
) -> MagicMock:
    accessory = MagicMock()
    accessory.id = accessory_id
    accessory.type = accessory_type
    accessory.detect_motion = detect_motion
    return accessory


def _mock_room(room_id: int, accessories: list[MagicMock]) -> MagicMock:
    room = MagicMock()
    room.id = room_id
    room.accessories = accessories
    return room


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


async def test_async_setup_entry_creates_expected_entities() -> None:
    """Device-level and accessory-level binary sensors are created correctly.

    A room with two accessories (one Thermostat, one IndoorAirSensor) should
    only produce a Room Motion entity for the IndoorAirSensor accessory.
    """
    device = _mock_device()
    location = MagicMock(location_id="location1", devices=[device])

    thermostat_accessory = _mock_accessory(0, "Thermostat")
    sensor_accessory = _mock_accessory(1, "IndoorAirSensor", detect_motion=True)
    room = _mock_room(0, [thermostat_accessory, sensor_accessory])

    coordinator = MagicMock()
    coordinator.data.locations = [location]
    coordinator.data.rooms_dict = {device.mac_id: {0: room}}

    entry = MagicMock()
    entry.runtime_data = coordinator

    added: list[list] = []
    async_add_entities = MagicMock(
        side_effect=lambda entities: added.append(list(entities))
    )

    await async_setup_entry(MagicMock(), entry, async_add_entities)

    device_entities, accessory_entities = added
    assert {e.entity_description.key for e in device_entities} == {
        "vacation_hold",
        "device_pairing_enabled",
    }
    assert len(accessory_entities) == 1
    assert accessory_entities[0].entity_description.key == "room_motion"


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

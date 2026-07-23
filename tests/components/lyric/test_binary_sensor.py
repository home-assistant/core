"""Tests for the Honeywell Lyric binary sensor platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.lyric.binary_sensor import (
    ACCESSORY_BINARY_SENSORS,
    DEVICE_BINARY_SENSORS,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MAC_ID, async_setup_lyric_entry

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


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


async def test_device_pairing_enabled_created(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_credentials: None,
    mock_lyric_api: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Device Pairing Enabled is created via a real config entry setup.

    Exercises the full boundary: real HTTP responses (mocked at the aiohttp
    transport level with the actual live payload shape) -> real aiolyric
    parsing -> real coordinator -> real entity setup -> registered state.
    devicePairingEnabled has no known aiolyric field-name mismatch, so this
    passes against the currently-pinned release.
    """
    await async_setup_lyric_entry(hass, mock_config_entry)

    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", "lyric", f"{MAC_ID}_device_pairing_enabled"
    )
    assert entity_id
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "on"


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
async def test_vacation_hold_created(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_credentials: None,
    mock_lyric_api: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Vacation Hold should read "on" via a real config entry setup.

    The mocked /locations response has vacationHold.Enabled = True (the
    real live shape), so this documents the currently-pinned aiolyric bug
    rather than hiding it - it fails today for the same reason the real
    entity does, and will start passing once the dependency is fixed.
    """
    await async_setup_lyric_entry(hass, mock_config_entry)

    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", "lyric", f"{MAC_ID}_vacation_hold"
    )
    assert entity_id
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "on"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "aiolyric 2.1.1's LyricPriority.current_priority reads JSON key "
        "'currentPriority' and LyricAccessory.type reads 'type', but "
        "Resideo's live API returns 'priority' and 'sensorType'. Fixed "
        "upstream in timmo001/aiolyric#165; once that's released and the "
        "manifest pin is bumped, this will start passing for real and this "
        "marker must be removed."
    ),
)
async def test_room_motion_created(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_credentials: None,
    mock_lyric_api: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Room Motion should be created via a real config entry setup.

    The mocked /priority response uses the real live shape ("priority",
    "sensorType"), so under the currently-pinned aiolyric this entity
    doesn't get created at all - documents the gap instead of hiding it.
    """
    await async_setup_lyric_entry(hass, mock_config_entry)

    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", "lyric", f"{MAC_ID}_room1_acc1_room_motion"
    )
    assert entity_id
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "on"


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

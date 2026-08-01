"""Test Subaru binary sensors."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.subaru.binary_sensor import (
    BINARY_SENSORS,
    EV_CHARGING_BINARY_SENSOR,
    EV_PLUG_BINARY_SENSOR,
    LOCK_STATUS_KEYS,
    MIL_TRANSLATION_KEYS,
    OVERALL_HEALTH_BINARY_SENSOR,
    _is_charging,
    _is_open,
    _is_plugged_in,
    _is_unlocked,
    _mil_is_on,
    _vehicle_status_is_on,
)
from homeassistant.components.subaru.const import DOMAIN, VEHICLE_HEALTH, VEHICLE_STATUS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .api_responses import (
    TEST_VIN_1_G1,
    TEST_VIN_2_EV,
    TEST_VIN_3_G3,
    TEST_VIN_4_G4,
    VEHICLE_DATA,
    VEHICLE_STATUS_G3,
)
from .conftest import setup_subaru_config_entry

from tests.common import MockConfigEntry, snapshot_platform


def _unique_id(vin: str, key: str) -> str:
    return f"{vin}_{key}"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    subaru_config_entry: MockConfigEntry,
) -> None:
    """Snapshot all binary sensors created for an EV vehicle."""
    with patch(
        "homeassistant.components.subaru.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_subaru_config_entry(hass, subaru_config_entry)
    await snapshot_platform(
        hass, entity_registry, snapshot, subaru_config_entry.entry_id
    )


@pytest.mark.parametrize("feature", ["TPMS_MIL", "CEL_MIL"])
@pytest.mark.usefixtures("ev_entry")
async def test_mil_entities_disabled_by_default(
    entity_registry: er.EntityRegistry,
    feature: str,
) -> None:
    """MIL entities are created for reported MIL features and disabled by default."""
    entity_id = entity_registry.async_get_entity_id(
        BINARY_SENSOR_DOMAIN, DOMAIN, _unique_id(TEST_VIN_2_EV, feature)
    )
    assert entity_id is not None
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entry.translation_key == MIL_TRANSLATION_KEYS[feature]


@pytest.mark.parametrize(
    "key",
    [desc.key for desc in BINARY_SENSORS]
    + [OVERALL_HEALTH_BINARY_SENSOR.key, EV_PLUG_BINARY_SENSOR.key],
)
async def test_no_binary_sensors_for_g1(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    subaru_config_entry: MockConfigEntry,
    key: str,
) -> None:
    """Gen1 vehicles do not get any binary sensors (no door/lock/health data)."""
    await setup_subaru_config_entry(
        hass,
        subaru_config_entry,
        vehicle_list=[TEST_VIN_1_G1],
        vehicle_data=VEHICLE_DATA[TEST_VIN_1_G1],
    )
    assert (
        entity_registry.async_get_entity_id(
            BINARY_SENSOR_DOMAIN, DOMAIN, _unique_id(TEST_VIN_1_G1, key)
        )
        is None
    )


async def test_no_ev_plug_binary_sensor_for_g3(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    subaru_config_entry: MockConfigEntry,
) -> None:
    """Non-EV vehicles do not get the EV plug binary sensor."""
    await setup_subaru_config_entry(
        hass,
        subaru_config_entry,
        vehicle_list=[TEST_VIN_3_G3],
        vehicle_data=VEHICLE_DATA[TEST_VIN_3_G3],
        vehicle_status=VEHICLE_STATUS_G3,
    )
    assert (
        entity_registry.async_get_entity_id(
            BINARY_SENSOR_DOMAIN,
            DOMAIN,
            _unique_id(TEST_VIN_3_G3, EV_PLUG_BINARY_SENSOR.key),
        )
        is None
    )


@pytest.mark.parametrize("key", list(LOCK_STATUS_KEYS))
async def test_no_lock_sensors_when_unsupported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    subaru_config_entry: MockConfigEntry,
    key: str,
) -> None:
    """Lock sensors aren't created for a vehicle whose status omits them.

    VEHICLE_STATUS_G3 has no LOCK_* keys, matching a real vehicle without
    lock-status support -- subarulink omits these fields entirely rather
    than reporting them as unknown.
    """
    await setup_subaru_config_entry(
        hass,
        subaru_config_entry,
        vehicle_list=[TEST_VIN_3_G3],
        vehicle_data=VEHICLE_DATA[TEST_VIN_3_G3],
        vehicle_status=VEHICLE_STATUS_G3,
    )
    assert (
        entity_registry.async_get_entity_id(
            BINARY_SENSOR_DOMAIN, DOMAIN, _unique_id(TEST_VIN_3_G3, key)
        )
        is None
    )


async def test_overall_health_unknown_without_vehicle_health(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    subaru_config_entry: MockConfigEntry,
) -> None:
    """Overall vehicle health is `unknown` when the API has not yet returned health data."""
    await setup_subaru_config_entry(
        hass,
        subaru_config_entry,
        vehicle_list=[TEST_VIN_3_G3],
        vehicle_data=VEHICLE_DATA[TEST_VIN_3_G3],
        vehicle_status=VEHICLE_STATUS_G3,
    )
    overall = entity_registry.async_get_entity_id(
        BINARY_SENSOR_DOMAIN, DOMAIN, _unique_id(TEST_VIN_3_G3, "health_istrouble")
    )
    assert overall is not None
    state = hass.states.get(overall)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_binary_sensors_created_for_g4(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    subaru_config_entry: MockConfigEntry,
) -> None:
    """Gen4 vehicles get binary sensors, same as Gen2/Gen3."""
    await setup_subaru_config_entry(
        hass,
        subaru_config_entry,
        vehicle_list=[TEST_VIN_4_G4],
        vehicle_data=VEHICLE_DATA[TEST_VIN_4_G4],
        vehicle_status=VEHICLE_STATUS_G3,
    )
    assert (
        entity_registry.async_get_entity_id(
            BINARY_SENSOR_DOMAIN, DOMAIN, _unique_id(TEST_VIN_4_G4, "health_istrouble")
        )
        is not None
    )


@pytest.mark.usefixtures("ev_entry")
async def test_ev_charging_disabled_by_default(
    entity_registry: er.EntityRegistry,
) -> None:
    """The EV charging sensor is disabled by default, unlike the EV plug sensor."""
    entity_id = entity_registry.async_get_entity_id(
        BINARY_SENSOR_DOMAIN,
        DOMAIN,
        _unique_id(TEST_VIN_2_EV, EV_CHARGING_BINARY_SENSOR.key),
    )
    assert entity_id is not None
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize("key", ["health_istrouble", "DOOR_FRONT_LEFT_POSITION"])
async def test_entities_unavailable_when_vehicle_data_fetch_fails(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    subaru_config_entry: MockConfigEntry,
    key: str,
) -> None:
    """Setup survives a vehicle whose data fetch fails; its entities go unavailable.

    _refresh_subaru_data only adds coordinator.data[vin] when the per-vehicle
    API call succeeds, so a failure must not crash setup for descriptions
    that are created unconditionally (e.g. the door/health sensors).
    """
    await setup_subaru_config_entry(hass, subaru_config_entry, vehicle_status={})
    assert subaru_config_entry.state is ConfigEntryState.LOADED

    entity_id = entity_registry.async_get_entity_id(
        BINARY_SENSOR_DOMAIN, DOMAIN, _unique_id(TEST_VIN_2_EV, key)
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("CLOSED", False),
        ("CLOSE", False),
        ("OPEN", True),
        ("VENTED", True),
    ],
)
def test_is_open(status: str, expected: bool) -> None:
    """Anything not in the closed set counts as open."""
    assert _is_open(status) is expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("LOCKED", False),
        ("UNLOCKED", True),
    ],
)
def test_is_unlocked(status: str, expected: bool) -> None:
    """Anything other than LOCKED counts as unlocked."""
    assert _is_unlocked(status) is expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("CHARGING", True),
        ("LOCKED_CONNECTED", True),
        ("UNLOCKED_CONNECTED", True),
        ("UNPLUGGED", False),
    ],
)
def test_is_plugged_in(status: str, expected: bool) -> None:
    """Only documented connected states count as plugged in."""
    assert _is_plugged_in(status) is expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("CHARGING", True),
        ("NOT_CHARGING", False),
        ("UNPLUGGED", False),
    ],
)
def test_is_charging(status: str, expected: bool) -> None:
    """Only CHARGING counts as actively charging."""
    assert _is_charging(status) is expected


@pytest.mark.parametrize(
    ("raw_status", "expected"),
    [
        ("CLOSED", False),
        ("closed", False),
        ("OPEN", True),
        ("UNKNOWN", None),
        ("UNAVAILABLE", None),
        ("NOT_EQUIPPED", None),
    ],
)
def test_vehicle_status_is_on_getter(raw_status: str, expected: bool | None) -> None:
    """The getter normalizes case and short-circuits on sentinel values."""
    getter = _vehicle_status_is_on("DOOR_FRONT_LEFT_POSITION", _is_open)
    vehicle_data = {VEHICLE_STATUS: {"DOOR_FRONT_LEFT_POSITION": raw_status}}
    assert getter(vehicle_data) is expected


def test_vehicle_status_is_on_getter_missing_key() -> None:
    """The getter returns None when the field is absent entirely."""
    getter = _vehicle_status_is_on("DOOR_FRONT_LEFT_POSITION", _is_open)
    assert getter({VEHICLE_STATUS: {}}) is None
    assert getter({}) is None


@pytest.mark.parametrize(
    ("feature_health", "expected"),
    [
        ({"ISTROUBLE": True, "ONDATE": None}, True),
        ({"ISTROUBLE": False, "ONDATE": None}, False),
        ({}, None),
    ],
)
def test_mil_is_on(feature_health: dict, expected: bool | None) -> None:
    """The MIL getter reads ISTROUBLE for the requested feature only."""
    getter = _mil_is_on("CEL_MIL")
    vehicle_data = {VEHICLE_HEALTH: {"FEATURES": {"CEL_MIL": feature_health}}}
    assert getter(vehicle_data) is expected


def test_mil_is_on_missing_feature() -> None:
    """The MIL getter returns None when the vehicle never reported that MIL."""
    getter = _mil_is_on("CEL_MIL")
    assert getter({VEHICLE_HEALTH: {"FEATURES": {}}}) is None
    assert getter({}) is None

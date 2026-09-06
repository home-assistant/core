"""Test Subaru binary sensors."""

import copy
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
)
from homeassistant.components.subaru.const import DOMAIN, VEHICLE_STATUS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .api_responses import (
    TEST_VIN_1_G1,
    TEST_VIN_2_EV,
    TEST_VIN_3_G3,
    TEST_VIN_4_G4,
    VEHICLE_DATA,
    VEHICLE_STATUS_EV,
    VEHICLE_STATUS_G3,
)
from .conftest import setup_subaru_config_entry

from tests.common import MockConfigEntry, snapshot_platform


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
        BINARY_SENSOR_DOMAIN, DOMAIN, f"{TEST_VIN_2_EV}_{feature}"
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
            BINARY_SENSOR_DOMAIN, DOMAIN, f"{TEST_VIN_1_G1}_{key}"
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
            f"{TEST_VIN_3_G3}_{EV_PLUG_BINARY_SENSOR.key}",
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
            BINARY_SENSOR_DOMAIN, DOMAIN, f"{TEST_VIN_3_G3}_{key}"
        )
        is None
    )


@pytest.mark.parametrize("not_equipped", ["NOT_EQUIPPED", "not_equipped"])
async def test_door_not_equipped_gets_no_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    subaru_config_entry: MockConfigEntry,
    not_equipped: str,
) -> None:
    """A door reported as NOT_EQUIPPED gets no entity, unlike a failed fetch.

    Unlike windows/locks, doors are always present in vehicle_status, so
    a per-door NOT_EQUIPPED value (not the key's absence) is what signals
    the trim genuinely lacks that sensor. Checked case-insensitively.
    """
    vehicle_status = copy.deepcopy(VEHICLE_STATUS_EV)
    vehicle_status[VEHICLE_STATUS]["DOOR_ENGINE_HOOD_POSITION"] = not_equipped
    await setup_subaru_config_entry(
        hass, subaru_config_entry, vehicle_status=vehicle_status
    )
    assert (
        entity_registry.async_get_entity_id(
            BINARY_SENSOR_DOMAIN,
            DOMAIN,
            f"{TEST_VIN_2_EV}_DOOR_ENGINE_HOOD_POSITION",
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id(
            BINARY_SENSOR_DOMAIN,
            DOMAIN,
            f"{TEST_VIN_2_EV}_DOOR_FRONT_LEFT_POSITION",
        )
        is not None
    )


async def test_no_ev_charging_sensor_when_unsupported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    subaru_config_entry: MockConfigEntry,
) -> None:
    """EV charging isn't created for an EV that doesn't report it, unlike EV plug."""
    vehicle_status = copy.deepcopy(VEHICLE_STATUS_EV)
    del vehicle_status[VEHICLE_STATUS]["EV_CHARGER_STATE_TYPE"]
    await setup_subaru_config_entry(
        hass, subaru_config_entry, vehicle_status=vehicle_status
    )
    assert (
        entity_registry.async_get_entity_id(
            BINARY_SENSOR_DOMAIN,
            DOMAIN,
            f"{TEST_VIN_2_EV}_{EV_CHARGING_BINARY_SENSOR.key}",
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id(
            BINARY_SENSOR_DOMAIN,
            DOMAIN,
            f"{TEST_VIN_2_EV}_{EV_PLUG_BINARY_SENSOR.key}",
        )
        is not None
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
        BINARY_SENSOR_DOMAIN, DOMAIN, f"{TEST_VIN_3_G3}_health_istrouble"
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
            BINARY_SENSOR_DOMAIN, DOMAIN, f"{TEST_VIN_4_G4}_health_istrouble"
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
        f"{TEST_VIN_2_EV}_{EV_CHARGING_BINARY_SENSOR.key}",
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
        BINARY_SENSOR_DOMAIN, DOMAIN, f"{TEST_VIN_2_EV}_{key}"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_no_window_or_lock_entities_when_vehicle_data_fetch_fails(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    subaru_config_entry: MockConfigEntry,
) -> None:
    """Unlike doors, windows/locks aren't created when the initial fetch fails."""
    await setup_subaru_config_entry(hass, subaru_config_entry, vehicle_status={})
    assert (
        entity_registry.async_get_entity_id(
            BINARY_SENSOR_DOMAIN, DOMAIN, f"{TEST_VIN_2_EV}_WINDOW_FRONT_LEFT_STATUS"
        )
        is None
    )


@pytest.mark.parametrize(
    ("status", "expected_state"),
    [
        ("CLOSED", STATE_OFF),
        ("CLOSE", STATE_OFF),
        ("closed", STATE_OFF),
        ("OPEN", STATE_ON),
        ("VENTED", STATE_ON),
        ("UNKNOWN", STATE_UNKNOWN),
        ("UNAVAILABLE", STATE_UNKNOWN),
    ],
)
async def test_door_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    subaru_config_entry: MockConfigEntry,
    status: str,
    expected_state: str,
) -> None:
    """Door state reflects the raw status, case-insensitively; sentinels are unknown."""
    vehicle_status = copy.deepcopy(VEHICLE_STATUS_EV)
    vehicle_status[VEHICLE_STATUS]["DOOR_FRONT_LEFT_POSITION"] = status
    await setup_subaru_config_entry(
        hass, subaru_config_entry, vehicle_status=vehicle_status
    )
    entity_id = entity_registry.async_get_entity_id(
        BINARY_SENSOR_DOMAIN, DOMAIN, f"{TEST_VIN_2_EV}_DOOR_FRONT_LEFT_POSITION"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("status", "expected_state"),
    [
        ("LOCKED", STATE_OFF),
        ("UNLOCKED", STATE_ON),
    ],
)
async def test_lock_sensor_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    subaru_config_entry: MockConfigEntry,
    status: str,
    expected_state: str,
) -> None:
    """Lock-status sensor is on when unlocked."""
    vehicle_status = copy.deepcopy(VEHICLE_STATUS_EV)
    vehicle_status[VEHICLE_STATUS]["LOCK_FRONT_LEFT_STATUS"] = status
    await setup_subaru_config_entry(
        hass, subaru_config_entry, vehicle_status=vehicle_status
    )
    entity_id = entity_registry.async_get_entity_id(
        BINARY_SENSOR_DOMAIN, DOMAIN, f"{TEST_VIN_2_EV}_LOCK_FRONT_LEFT_STATUS"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("status", "expected_state"),
    [
        ("CHARGING", STATE_ON),
        ("LOCKED_CONNECTED", STATE_ON),
        ("UNLOCKED_CONNECTED", STATE_ON),
        ("UNPLUGGED", STATE_OFF),
    ],
)
async def test_ev_plug_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    subaru_config_entry: MockConfigEntry,
    status: str,
    expected_state: str,
) -> None:
    """EV plug sensor is on for any documented connected state."""
    vehicle_status = copy.deepcopy(VEHICLE_STATUS_EV)
    vehicle_status[VEHICLE_STATUS]["EV_IS_PLUGGED_IN"] = status
    await setup_subaru_config_entry(
        hass, subaru_config_entry, vehicle_status=vehicle_status
    )
    entity_id = entity_registry.async_get_entity_id(
        BINARY_SENSOR_DOMAIN, DOMAIN, f"{TEST_VIN_2_EV}_EV_IS_PLUGGED_IN"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("status", "expected_state"),
    [
        ("CHARGING", STATE_ON),
        ("NOT_CHARGING", STATE_OFF),
        ("UNPLUGGED", STATE_OFF),
    ],
)
async def test_ev_charging_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    subaru_config_entry: MockConfigEntry,
    status: str,
    expected_state: str,
) -> None:
    """EV charging sensor is on only while actively CHARGING."""
    vehicle_status = copy.deepcopy(VEHICLE_STATUS_EV)
    vehicle_status[VEHICLE_STATUS]["EV_CHARGER_STATE_TYPE"] = status
    await setup_subaru_config_entry(
        hass, subaru_config_entry, vehicle_status=vehicle_status
    )
    entity_id = entity_registry.async_get_entity_id(
        BINARY_SENSOR_DOMAIN, DOMAIN, f"{TEST_VIN_2_EV}_EV_CHARGER_STATE_TYPE"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "ev_entry")
async def test_mil_sensor_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """MIL sensor reflects the per-feature ISTROUBLE flag."""
    on_entity = entity_registry.async_get_entity_id(
        BINARY_SENSOR_DOMAIN, DOMAIN, f"{TEST_VIN_2_EV}_CEL_MIL"
    )
    off_entity = entity_registry.async_get_entity_id(
        BINARY_SENSOR_DOMAIN, DOMAIN, f"{TEST_VIN_2_EV}_TPMS_MIL"
    )
    assert on_entity is not None
    assert off_entity is not None
    on_state = hass.states.get(on_entity)
    off_state = hass.states.get(off_entity)
    assert on_state is not None
    assert off_state is not None
    assert on_state.state == STATE_ON
    assert off_state.state == STATE_OFF

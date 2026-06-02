"""Test Subaru binary sensors."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.subaru.binary_sensor import (
    BINARY_SENSORS,
    MIL_TRANSLATION_KEYS,
)
from homeassistant.components.subaru.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .api_responses import (
    TEST_VIN_1_G1,
    TEST_VIN_2_EV,
    TEST_VIN_3_G3,
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


async def test_no_binary_sensors_for_g1(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    subaru_config_entry: MockConfigEntry,
) -> None:
    """Gen1 vehicles do not get any binary sensors (no door/lock/health data)."""
    await setup_subaru_config_entry(
        hass,
        subaru_config_entry,
        vehicle_list=[TEST_VIN_1_G1],
        vehicle_data=VEHICLE_DATA[TEST_VIN_1_G1],
    )
    for desc in BINARY_SENSORS:
        assert (
            entity_registry.async_get_entity_id(
                BINARY_SENSOR_DOMAIN, DOMAIN, _unique_id(TEST_VIN_1_G1, desc.key)
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
            BINARY_SENSOR_DOMAIN, DOMAIN, _unique_id(TEST_VIN_3_G3, "EV_IS_PLUGGED_IN")
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

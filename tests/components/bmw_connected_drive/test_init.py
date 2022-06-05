"""Test Axis component setup process."""
from unittest.mock import patch

import pytest

from homeassistant.components.bmw_connected_drive.const import DOMAIN as BMW_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import FIXTURE_CONFIG_ENTRY

from tests.common import MockConfigEntry

VIN = "WBYYYYYYYYYYYYYYY"
VEHICLE_NAME = "i3 (+ REX)"
VEHICLE_NAME_SLUG = "i3_rex"


@pytest.mark.parametrize(
    "entitydata,old_unique_id,new_unique_id",
    [
        (
            {
                "domain": SENSOR_DOMAIN,
                "platform": BMW_DOMAIN,
                "unique_id": f"{VIN}-charging_level_hv",
                "suggested_object_id": f"{VEHICLE_NAME} charging_level_hv",
                "disabled_by": None,
            },
            f"{VIN}-charging_level_hv",
            f"{VIN}-remaining_battery_percent",
        ),
        (
            {
                "domain": SENSOR_DOMAIN,
                "platform": BMW_DOMAIN,
                "unique_id": f"{VIN}-remaining_range_total",
                "suggested_object_id": f"{VEHICLE_NAME} remaining_range_total",
                "disabled_by": None,
            },
            f"{VIN}-remaining_range_total",
            f"{VIN}-remaining_range_total",
        ),
    ],
)
async def test_migrate_unique_ids(
    hass: HomeAssistant,
    entitydata: dict,
    old_unique_id: str,
    new_unique_id: str,
) -> None:
    """Test successful migration of entity unique_ids."""
    mock_config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    mock_config_entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)
    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        **entitydata,
        config_entry=mock_config_entry,
    )

    assert entity.unique_id == old_unique_id

    with patch(
        "bimmer_connected.account.MyBMWAccount.get_vehicles",
        return_value=[],
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_migrated = entity_registry.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == new_unique_id


@pytest.mark.parametrize(
    "entitydata,old_unique_id,new_unique_id",
    [
        (
            {
                "domain": SENSOR_DOMAIN,
                "platform": BMW_DOMAIN,
                "unique_id": f"{VIN}-charging_level_hv",
                "suggested_object_id": f"{VEHICLE_NAME} charging_level_hv",
                "disabled_by": None,
            },
            f"{VIN}-charging_level_hv",
            f"{VIN}-remaining_battery_percent",
        ),
    ],
)
async def test_dont_migrate_unique_ids(
    hass: HomeAssistant,
    entitydata: dict,
    old_unique_id: str,
    new_unique_id: str,
) -> None:
    """Test successful migration of entity unique_ids."""
    mock_config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    mock_config_entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)

    # create existing entry with new_unique_id
    existing_entity = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        BMW_DOMAIN,
        unique_id=f"{VIN}-remaining_battery_percent",
        suggested_object_id=f"{VEHICLE_NAME} remaining_battery_percent",
        config_entry=mock_config_entry,
    )

    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        **entitydata,
        config_entry=mock_config_entry,
    )

    assert entity.unique_id == old_unique_id

    with patch(
        "bimmer_connected.account.MyBMWAccount.get_vehicles",
        return_value=[],
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_migrated = entity_registry.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == old_unique_id

    entity_not_changed = entity_registry.async_get(existing_entity.entity_id)
    assert entity_not_changed
    assert entity_not_changed.unique_id == new_unique_id

    assert entity_migrated != entity_not_changed

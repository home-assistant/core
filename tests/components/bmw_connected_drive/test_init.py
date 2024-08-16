"""Test Axis component setup process."""

from copy import deepcopy
from unittest.mock import patch

import pytest

from homeassistant.components.bmw_connected_drive import DEFAULT_OPTIONS
from homeassistant.components.bmw_connected_drive.const import (
    CONF_READ_ONLY,
    DOMAIN as BMW_DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import FIXTURE_CONFIG_ENTRY

from tests.common import MockConfigEntry

VIN = "WBYYYYYYYYYYYYYYY"
VEHICLE_NAME = "i3 (+ REX)"
VEHICLE_NAME_SLUG = "i3_rex"


@pytest.mark.usefixtures("bmw_fixture")
@pytest.mark.parametrize(
    "options",
    [
        DEFAULT_OPTIONS,
        {"other_value": 1, **DEFAULT_OPTIONS},
        {},
    ],
)
async def test_migrate_options(
    hass: HomeAssistant,
    options: dict,
) -> None:
    """Test successful migration of options."""

    config_entry = deepcopy(FIXTURE_CONFIG_ENTRY)
    config_entry["options"] = options

    mock_config_entry = MockConfigEntry(**config_entry)
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(
        hass.config_entries.async_get_entry(mock_config_entry.entry_id).options
    ) == len(DEFAULT_OPTIONS)


@pytest.mark.usefixtures("bmw_fixture")
async def test_migrate_options_from_data(hass: HomeAssistant) -> None:
    """Test successful migration of options."""

    config_entry = deepcopy(FIXTURE_CONFIG_ENTRY)
    config_entry["options"] = {}
    config_entry["data"].update({CONF_READ_ONLY: False})

    mock_config_entry = MockConfigEntry(**config_entry)
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    updated_config_entry = hass.config_entries.async_get_entry(
        mock_config_entry.entry_id
    )
    assert len(updated_config_entry.options) == len(DEFAULT_OPTIONS)
    assert CONF_READ_ONLY not in updated_config_entry.data


@pytest.mark.parametrize(
    ("entitydata", "old_unique_id", "new_unique_id"),
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
            f"{VIN}-fuel_and_battery.remaining_battery_percent",
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
            f"{VIN}-fuel_and_battery.remaining_range_total",
        ),
        (
            {
                "domain": SENSOR_DOMAIN,
                "platform": BMW_DOMAIN,
                "unique_id": f"{VIN}-mileage",
                "suggested_object_id": f"{VEHICLE_NAME} mileage",
                "disabled_by": None,
            },
            f"{VIN}-mileage",
            f"{VIN}-mileage",
        ),
    ],
)
async def test_migrate_unique_ids(
    hass: HomeAssistant,
    entitydata: dict,
    old_unique_id: str,
    new_unique_id: str,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test successful migration of entity unique_ids."""
    confg_entry = deepcopy(FIXTURE_CONFIG_ENTRY)
    mock_config_entry = MockConfigEntry(**confg_entry)
    mock_config_entry.add_to_hass(hass)

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
    ("entitydata", "old_unique_id", "new_unique_id"),
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
            f"{VIN}-fuel_and_battery.remaining_battery_percent",
        ),
    ],
)
async def test_dont_migrate_unique_ids(
    hass: HomeAssistant,
    entitydata: dict,
    old_unique_id: str,
    new_unique_id: str,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test successful migration of entity unique_ids."""
    confg_entry = deepcopy(FIXTURE_CONFIG_ENTRY)
    mock_config_entry = MockConfigEntry(**confg_entry)
    mock_config_entry.add_to_hass(hass)

    # create existing entry with new_unique_id
    existing_entity = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        BMW_DOMAIN,
        unique_id=f"{VIN}-fuel_and_battery.remaining_battery_percent",
        suggested_object_id=f"{VEHICLE_NAME} fuel_and_battery.remaining_battery_percent",
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


@pytest.mark.usefixtures("bmw_fixture")
async def test_remove_stale_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test remove stale device registry entries."""
    config_entry = deepcopy(FIXTURE_CONFIG_ENTRY)
    mock_config_entry = MockConfigEntry(**config_entry)
    mock_config_entry.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(BMW_DOMAIN, "stale_device_id")},
    )
    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )

    assert len(device_entries) == 1
    device_entry = device_entries[0]
    assert device_entry.identifiers == {(BMW_DOMAIN, "stale_device_id")}

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )

    # Check that the test vehicles are still available but not the stale device
    assert len(device_entries) > 0
    remaining_device_identifiers = set().union(*(d.identifiers for d in device_entries))
    assert not {(BMW_DOMAIN, "stale_device_id")}.intersection(
        remaining_device_identifiers
    )

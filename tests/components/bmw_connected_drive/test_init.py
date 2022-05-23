"""Test Axis component setup process."""
from homeassistant.components.bmw_connected_drive import _async_migrate_entries
from homeassistant.components.bmw_connected_drive.const import DOMAIN as BMW_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_migrate_unique_ids(hass):
    """Test successful migration of entity unique_ids."""

    config_entry = MockConfigEntry(
        domain=BMW_DOMAIN,
        data={
            CONF_REGION: "rest_of_world",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
        },
    )

    registry = er.async_get(hass)

    # Create entity entry to migrate to new unique ID
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        BMW_DOMAIN,
        unique_id="WBYYYYYYYYYYYYYYY-charging_level_hv",
        suggested_object_id="i3 (+ REX) charging_level_hv",
        config_entry=config_entry,
    )
    # Create entity entry that shouldn't be migrated
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        BMW_DOMAIN,
        unique_id="WBYYYYYYYYYYYYYYY-remaining_range_total",
        suggested_object_id="i3  (+ REX) remaining_range_total",
        config_entry=config_entry,
    )

    # Verify data pre-migration
    assert (
        registry.async_get("sensor.i3_rex_charging_level_hv").unique_id
        == "WBYYYYYYYYYYYYYYY-charging_level_hv"
    )
    assert (
        registry.async_get("sensor.i3_rex_remaining_range_total").unique_id
        == "WBYYYYYYYYYYYYYYY-remaining_range_total"
    )

    await _async_migrate_entries(hass, config_entry)

    # Verify data after migration
    assert (
        registry.async_get("sensor.i3_rex_charging_level_hv").unique_id
        == "WBYYYYYYYYYYYYYYY-remaining_battery_percent"
    )
    assert (
        registry.async_get("sensor.i3_rex_remaining_range_total").unique_id
        == "WBYYYYYYYYYYYYYYY-remaining_range_total"
    )


async def test_migrate_previously_created_unique_ids(hass):
    """Test migration of entity unique_ids that have been created before (i.e. through custom component)."""

    config_entry = MockConfigEntry(
        domain=BMW_DOMAIN,
        data={
            CONF_REGION: "rest_of_world",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
        },
    )

    registry = er.async_get(hass)

    # Create entity entry to migrate to new unique ID
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        BMW_DOMAIN,
        unique_id="WBYYYYYYYYYYYYYYY-charging_level_hv",
        suggested_object_id="i3 (+ REX) charging_level_hv",
        config_entry=config_entry,
    )
    # Create entity entry that already exists
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        BMW_DOMAIN,
        unique_id="WBYYYYYYYYYYYYYYY-remaining_battery_percent",
        suggested_object_id="i3  (+ REX) remaining_battery_percent",
        config_entry=config_entry,
    )

    # Verify data pre-migration
    assert (
        registry.async_get("sensor.i3_rex_charging_level_hv").unique_id
        == "WBYYYYYYYYYYYYYYY-charging_level_hv"
    )
    assert (
        registry.async_get("sensor.i3_rex_remaining_battery_percent").unique_id
        == "WBYYYYYYYYYYYYYYY-remaining_battery_percent"
    )

    await _async_migrate_entries(hass, config_entry)

    # Verify data after migration. As sensor with new unique_id already exists, nothing should change
    assert (
        registry.async_get("sensor.i3_rex_charging_level_hv").unique_id
        == "WBYYYYYYYYYYYYYYY-charging_level_hv"
    )
    assert (
        registry.async_get("sensor.i3_rex_remaining_battery_percent").unique_id
        == "WBYYYYYYYYYYYYYYY-remaining_battery_percent"
    )

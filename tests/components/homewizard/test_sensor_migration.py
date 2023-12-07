"""Test sensor entity migration for HomeWizard."""


import pytest

from homeassistant.components.homewizard.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("device_fixture", "entitydata", "old_unique_id", "new_unique_id"),
    [
        (
            "HWE-SKT",
            {
                "domain": Platform.SENSOR,
                "platform": DOMAIN,
                "unique_id": "aabbccddeeff_total_power_import_t1_kwh",
            },
            "aabbccddeeff_total_power_import_t1_kwh",
            "aabbccddeeff_total_power_import_kwh",
        ),
        (
            "HWE-SKT",
            {
                "domain": Platform.SENSOR,
                "platform": DOMAIN,
                "unique_id": "aabbccddeeff_total_power_export_t1_kwh",
            },
            "aabbccddeeff_total_power_export_t1_kwh",
            "aabbccddeeff_total_power_export_kwh",
        ),
    ],
)
@pytest.mark.usefixtures("mock_homewizardenergy")
async def test_sensor_migration(
    hass: HomeAssistant,
    entitydata: dict,
    old_unique_id: str,
    new_unique_id: str,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test total power T1 sensors are migrated."""
    mock_config_entry.add_to_hass(hass)

    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        **entitydata,
        config_entry=mock_config_entry,
    )

    assert entity.unique_id == old_unique_id

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_migrated = entity_registry.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == new_unique_id
    assert entity_migrated.previous_unique_id == old_unique_id


@pytest.mark.parametrize(
    ("device_fixture", "old_unique_id", "new_unique_id"),
    [
        (
            "HWE-SKT",
            "aabbccddeeff_total_power_import_t1_kwh",
            "aabbccddeeff_total_power_import_kwh",
        ),
        (
            "HWE-SKT",
            "aabbccddeeff_total_power_export_t1_kwh",
            "aabbccddeeff_total_power_export_kwh",
        ),
    ],
)
@pytest.mark.usefixtures("mock_homewizardenergy")
async def test_sensor_migration_does_not_trigger(
    hass: HomeAssistant,
    old_unique_id: str,
    new_unique_id: str,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test total power T1 sensors are not migrated when not needed."""
    mock_config_entry.add_to_hass(hass)

    old_entity: er.RegistryEntry = entity_registry.async_get_or_create(
        domain=Platform.SENSOR,
        platform=DOMAIN,
        unique_id=old_unique_id,
        config_entry=mock_config_entry,
    )

    new_entity: er.RegistryEntry = entity_registry.async_get_or_create(
        domain=Platform.SENSOR,
        platform=DOMAIN,
        unique_id=new_unique_id,
        config_entry=mock_config_entry,
    )

    assert old_entity.unique_id == old_unique_id
    assert new_entity.unique_id == new_unique_id

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity = entity_registry.async_get(old_entity.entity_id)
    assert entity
    assert entity.unique_id == old_unique_id
    assert entity.previous_unique_id is None

    entity = entity_registry.async_get(new_entity.entity_id)
    assert entity
    assert entity.unique_id == new_unique_id
    assert entity.previous_unique_id is None

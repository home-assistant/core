"""Test init of Satel Integra integration."""

from unittest.mock import AsyncMock

from homeassistant.components.satel_integra.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, RegistryEntryWithDefaults, mock_registry

ENTITY_PARTITION = "alarm_panel.home"
ENTITY_ZONE = "binary_sensor.zone"
ENTITY_OUTPUT = "binary_sensor.output"
ENTITY_SWITCHABLE_OUTPUT = "switch.siren"


async def test_unique_id_migration_from_single_config(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_satel: AsyncMock,
) -> None:
    """Test that the unique ID for a sleep switch is migrated to the new format."""

    mock_config_entry.add_to_hass(hass)

    mock_registry(
        hass,
        {
            ENTITY_PARTITION: RegistryEntryWithDefaults(
                entity_id=ENTITY_PARTITION,
                unique_id="satel_alarm_panel_1",
                platform=DOMAIN,
                config_entry_id=mock_config_entry.entry_id,
            ),
            ENTITY_ZONE: RegistryEntryWithDefaults(
                entity_id=ENTITY_ZONE,
                unique_id="satel_zone_1",
                platform=DOMAIN,
                config_entry_id=mock_config_entry.entry_id,
            ),
            ENTITY_OUTPUT: RegistryEntryWithDefaults(
                entity_id=ENTITY_OUTPUT,
                unique_id="satel_output_1",
                platform=DOMAIN,
                config_entry_id=mock_config_entry.entry_id,
            ),
            ENTITY_SWITCHABLE_OUTPUT: RegistryEntryWithDefaults(
                entity_id=ENTITY_SWITCHABLE_OUTPUT,
                unique_id="satel_switch_1",
                platform=DOMAIN,
                config_entry_id=mock_config_entry.entry_id,
            ),
        },
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)

    partition = ent_reg.async_get(ENTITY_PARTITION)
    assert partition.unique_id == f"{mock_config_entry.entry_id}_alarm_panel_1"

    zone = ent_reg.async_get(ENTITY_ZONE)
    assert zone.unique_id == f"{mock_config_entry.entry_id}_zone_1"

    output = ent_reg.async_get(ENTITY_OUTPUT)
    assert output.unique_id == f"{mock_config_entry.entry_id}_output_1"

    switchable_output = ent_reg.async_get(ENTITY_SWITCHABLE_OUTPUT)
    assert switchable_output.unique_id == f"{mock_config_entry.entry_id}_switch_1"

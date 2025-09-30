"""Test init of Satel Integra integration."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_PANEL_DOMAIN
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.satel_integra.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from . import MOCK_ENTRY_ID

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("platform", "old_id", "new_id"),
    [
        (ALARM_PANEL_DOMAIN, "satel_alarm_panel_1", f"{MOCK_ENTRY_ID}_alarm_panel_1"),
        (BINARY_SENSOR_DOMAIN, "satel_zone_1", f"{MOCK_ENTRY_ID}_zone_1"),
        (BINARY_SENSOR_DOMAIN, "satel_output_1", f"{MOCK_ENTRY_ID}_output_1"),
        (SWITCH_DOMAIN, "satel_switch_1", f"{MOCK_ENTRY_ID}_switch_1"),
    ],
)
async def test_unique_id_migration_from_single_config(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_satel: AsyncMock,
    entity_reg: EntityRegistry,
    platform: str,
    old_id: str,
    new_id: str,
) -> None:
    """Test that the unique ID is migrated to the new format."""

    mock_config_entry.add_to_hass(hass)

    entity = entity_reg.async_get_or_create(
        platform,
        DOMAIN,
        old_id,
        config_entry=mock_config_entry,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity = entity_reg.async_get(entity.entity_id)
    assert entity.unique_id == new_id

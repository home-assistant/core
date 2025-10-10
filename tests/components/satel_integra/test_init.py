"""Test init of Satel Integra integration."""

from copy import deepcopy
from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_PANEL_DOMAIN
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.satel_integra.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from . import (
    CONF_OUTPUT_NUMBER,
    CONF_PARTITION_NUMBER,
    CONF_SWITCHABLE_OUTPUT_NUMBER,
    CONF_ZONE_NUMBER,
    MOCK_CONFIG_DATA,
    MOCK_CONFIG_OPTIONS,
    MOCK_ENTRY_ID,
    MOCK_OUTPUT_SUBENTRY,
    MOCK_PARTITION_SUBENTRY,
    MOCK_SWITCHABLE_OUTPUT_SUBENTRY,
    MOCK_ZONE_SUBENTRY,
)

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("original", "number_property"),
    [
        (MOCK_PARTITION_SUBENTRY, CONF_PARTITION_NUMBER),
        (MOCK_ZONE_SUBENTRY, CONF_ZONE_NUMBER),
        (MOCK_OUTPUT_SUBENTRY, CONF_OUTPUT_NUMBER),
        (MOCK_SWITCHABLE_OUTPUT_SUBENTRY, CONF_SWITCHABLE_OUTPUT_NUMBER),
    ],
)
async def test_config_flow_migration_version_1_2(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_satel: AsyncMock,
    original: ConfigSubentry,
    number_property: str,
) -> None:
    """Test that the unique ID is migrated to the new format."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="192.168.0.2",
        data=MOCK_CONFIG_DATA,
        options=MOCK_CONFIG_OPTIONS,
        entry_id=MOCK_ENTRY_ID,
        version=1,
        minor_version=1,
    )
    config_entry.subentries = deepcopy({original.subentry_id: original})

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.version == 2
    assert config_entry.minor_version == 1

    subentry = config_entry.subentries.get(original.subentry_id)
    assert subentry is not None
    assert subentry.title == f"{original.title} ({original.data[number_property]})"


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
    mock_satel: AsyncMock,
    entity_registry: EntityRegistry,
    platform: str,
    old_id: str,
    new_id: str,
) -> None:
    """Test that the unique ID is migrated to the new format."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="192.168.0.2",
        data=MOCK_CONFIG_DATA,
        options=MOCK_CONFIG_OPTIONS,
        entry_id=MOCK_ENTRY_ID,
        version=1,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    entity = entity_registry.async_get_or_create(
        platform,
        DOMAIN,
        old_id,
        config_entry=config_entry,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity = entity_registry.async_get(entity.entity_id)

    assert entity is not None
    assert entity.unique_id == new_id

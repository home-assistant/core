"""Test Habitica sensor platform."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.habitica.const import DOMAIN
from homeassistant.components.habitica.sensor import HabitipySensorEntity
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def sensor_only() -> Generator[None]:
    """Enable only the sensor platform."""
    with patch(
        "homeassistant.components.habitica.PLATFORMS",
        [Platform.SENSOR],
    ):
        yield


@pytest.mark.usefixtures("habitica", "entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the Habitica sensor platform."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.usefixtures("habitica", "entity_registry_enabled_by_default")
async def test_sensor_deprecation_issue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test task sensor deprecation issue."""

    with patch(
        "homeassistant.components.habitica.sensor.entity_used_in", return_value=True
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.LOADED

        assert issue_registry.async_get_issue(
            domain=DOMAIN,
            issue_id=f"deprecated_task_entity_{HabitipySensorEntity.TODOS}",
        )
        assert issue_registry.async_get_issue(
            domain=DOMAIN,
            issue_id=f"deprecated_task_entity_{HabitipySensorEntity.DAILIES}",
        )

"""Test Habitica sensor platform."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.habitica.const import DOMAIN
from homeassistant.components.habitica.sensor import HabiticaSensorEntity
from homeassistant.components.sensor.const import DOMAIN as SENSOR_DOMAIN
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

    for entity in (
        ("test_user_habits", "habits"),
        ("test_user_rewards", "rewards"),
        ("test_user_max_health", "health_max"),
    ):
        entity_registry.async_get_or_create(
            SENSOR_DOMAIN,
            DOMAIN,
            f"a380546a-94be-4b8e-8a0b-23e0d5c03303_{entity[1]}",
            suggested_object_id=entity[0],
            disabled_by=None,
        )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "key"),
    [
        ("test_user_habits", HabiticaSensorEntity.HABITS),
        ("test_user_rewards", HabiticaSensorEntity.REWARDS),
        ("test_user_max_health", HabiticaSensorEntity.HEALTH_MAX),
    ],
)
@pytest.mark.usefixtures("habitica", "entity_registry_enabled_by_default")
async def test_sensor_deprecation_issue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
    entity_id: str,
    key: HabiticaSensorEntity,
) -> None:
    """Test sensor deprecation issue."""
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        f"a380546a-94be-4b8e-8a0b-23e0d5c03303_{key}",
        suggested_object_id=entity_id,
        disabled_by=None,
    )

    assert entity_registry is not None
    with patch(
        "homeassistant.components.habitica.sensor.entity_used_in", return_value=True
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.LOADED

        assert entity_registry.async_get(f"sensor.{entity_id}") is not None
        assert issue_registry.async_get_issue(
            domain=DOMAIN,
            issue_id=f"deprecated_entity_{key}",
        )


@pytest.mark.parametrize(
    ("entity_id", "key"),
    [
        ("test_user_habits", HabiticaSensorEntity.HABITS),
        ("test_user_rewards", HabiticaSensorEntity.REWARDS),
        ("test_user_max_health", HabiticaSensorEntity.HEALTH_MAX),
    ],
)
@pytest.mark.usefixtures("habitica", "entity_registry_enabled_by_default")
async def test_sensor_deprecation_delete_disabled(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
    entity_id: str,
    key: HabiticaSensorEntity,
) -> None:
    """Test sensor deletion ."""

    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        f"a380546a-94be-4b8e-8a0b-23e0d5c03303_{key}",
        suggested_object_id=entity_id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    assert entity_registry is not None
    with patch(
        "homeassistant.components.habitica.sensor.entity_used_in", return_value=True
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.LOADED

        assert (
            issue_registry.async_get_issue(
                domain=DOMAIN,
                issue_id=f"deprecated_entity_{key}",
            )
            is None
        )

        assert entity_registry.async_get(f"sensor.{entity_id}") is None

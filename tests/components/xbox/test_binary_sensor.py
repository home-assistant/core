"""Test the Xbox binary_sensor platform."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.xbox.binary_sensor import XboxBinarySensor
from homeassistant.components.xbox.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def binary_sensor_only() -> Generator[None]:
    """Enable only the binary_sensor platform."""
    with patch(
        "homeassistant.components.xbox.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        yield


@pytest.mark.usefixtures("xbox_live_client", "entity_registry_enabled_by_default")
async def test_binary_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the Xbox binary_sensor platform."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "key"),
    [
        ("gsr_ae_in_multiplayer", XboxBinarySensor.IN_MULTIPLAYER),
        ("gsr_ae_in_party", XboxBinarySensor.IN_PARTY),
    ],
)
@pytest.mark.usefixtures("xbox_live_client", "entity_registry_enabled_by_default")
async def test_binary_sensor_deprecation_issue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
    entity_id: str,
    key: XboxBinarySensor,
) -> None:
    """Test sensor deprecation issue."""
    entity_registry.async_get_or_create(
        BINARY_SENSOR_DOMAIN,
        DOMAIN,
        f"271958441785640_{key}",
        suggested_object_id=entity_id,
        disabled_by=None,
    )

    assert entity_registry is not None
    with patch(
        "homeassistant.components.xbox.entity.entity_used_in", return_value=True
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.LOADED

        assert entity_registry.async_get(f"binary_sensor.{entity_id}") is not None
        assert issue_registry.async_get_issue(
            domain=DOMAIN,
            issue_id=f"deprecated_entity_271958441785640_{key}",
        )


@pytest.mark.parametrize(
    ("entity_id", "key"),
    [
        ("gsr_ae_in_multiplayer", XboxBinarySensor.IN_MULTIPLAYER),
        ("gsr_ae_in_party", XboxBinarySensor.IN_PARTY),
    ],
)
@pytest.mark.usefixtures("xbox_live_client", "entity_registry_enabled_by_default")
async def test_binary_sensor_deprecation_remove_disabled(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
    entity_id: str,
    key: XboxBinarySensor,
) -> None:
    """Test we remove a deprecated binary sensor."""

    entity_registry.async_get_or_create(
        BINARY_SENSOR_DOMAIN,
        DOMAIN,
        f"271958441785640_{key}",
        suggested_object_id=entity_id,
    )

    assert entity_registry is not None

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert entity_registry.async_get(f"binary_sensor.{entity_id}") is None

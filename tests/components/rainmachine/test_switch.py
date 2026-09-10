"""Test RainMachine switches."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.rainmachine.const import (
    CONF_ALLOW_INACTIVE_ZONES_TO_RUN,
    DOMAIN,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, snapshot_platform

LEGACY_ZONE_ENTITY_ID = "switch.12345_landscaping"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switches(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    config: dict[str, Any],
    config_entry: MockConfigEntry,
    client: AsyncMock,
) -> None:
    """Test switches."""
    with (
        patch("homeassistant.components.rainmachine.Client", return_value=client),
        patch("homeassistant.components.rainmachine.PLATFORMS", [Platform.SWITCH]),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_inactive_program_cannot_run_when_inactive_zones_are_allowed(
    hass: HomeAssistant,
    config: dict[str, Any],
    config_entry: MockConfigEntry,
    client: AsyncMock,
    controller: AsyncMock,
) -> None:
    """Test that the inactive-zone option does not apply to programs."""
    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_ALLOW_INACTIVE_ZONES_TO_RUN: True},
    )
    with (
        patch("homeassistant.components.rainmachine.Client", return_value=client),
        patch("homeassistant.components.rainmachine.PLATFORMS", [Platform.SWITCH]),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError, match="Cannot turn on an inactive program"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.12345_evening_program"},
            blocking=True,
        )
    controller.programs.start.assert_not_awaited()


async def test_existing_zone_switch_is_deprecated(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    config: dict[str, Any],
    config_entry: MockConfigEntry,
    client: AsyncMock,
    controller_mac: str,
) -> None:
    """Test an existing zone switch remains available during deprecation."""
    hass.config_entries.async_update_entry(config_entry, version=2)
    entity_registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        f"{controller_mac}_zone_1",
        suggested_object_id="12345_landscaping",
        config_entry=config_entry,
        original_name="Landscaping",
    )

    with (
        patch("homeassistant.components.rainmachine.Client", return_value=client),
        patch("homeassistant.components.rainmachine.PLATFORMS", [Platform.SWITCH]),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    assert hass.states.get(LEGACY_ZONE_ENTITY_ID) is not None
    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_zone_switch_{config_entry.entry_id}_1"
    )
    assert issue is not None
    assert issue.breaks_in_ha_version == "2027.4.0"
    assert issue.translation_key == "deprecated_zone_switch"
    assert issue.translation_placeholders == {
        "entity_id": LEGACY_ZONE_ENTITY_ID,
        "entity_name": "Landscaping",
        "replacement_entity_id": "valve.12345_landscaping",
    }


async def test_disabled_unused_zone_switch_is_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    config: dict[str, Any],
    config_entry: MockConfigEntry,
    client: AsyncMock,
    controller_mac: str,
) -> None:
    """Test a disabled unused deprecated zone switch is removed."""
    hass.config_entries.async_update_entry(config_entry, version=2)
    entity_registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        f"{controller_mac}_zone_1",
        suggested_object_id="12345_landscaping",
        config_entry=config_entry,
        disabled_by=er.RegistryEntryDisabler.USER,
        original_name="Landscaping",
    )

    with (
        patch("homeassistant.components.rainmachine.Client", return_value=client),
        patch("homeassistant.components.rainmachine.PLATFORMS", [Platform.SWITCH]),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    assert entity_registry.async_get(LEGACY_ZONE_ENTITY_ID) is None
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"deprecated_zone_switch_{config_entry.entry_id}_1"
        )
        is None
    )


async def test_referenced_disabled_zone_switch_is_retained(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    config: dict[str, Any],
    config_entry: MockConfigEntry,
    client: AsyncMock,
    controller_mac: str,
) -> None:
    """Test a referenced deprecated switch is retained even while disabled."""
    hass.config_entries.async_update_entry(config_entry, version=2)
    entity_registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        f"{controller_mac}_zone_1",
        suggested_object_id="12345_landscaping",
        config_entry=config_entry,
        disabled_by=er.RegistryEntryDisabler.USER,
        original_name="Landscaping",
    )

    with (
        patch("homeassistant.components.rainmachine.Client", return_value=client),
        patch("homeassistant.components.rainmachine.PLATFORMS", [Platform.SWITCH]),
        patch(
            "homeassistant.components.rainmachine.util.get_automations_and_scripts_using_entity",
            return_value=["- `automation.test`"],
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    assert entity_registry.async_get(LEGACY_ZONE_ENTITY_ID) is not None
    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_zone_switch_{config_entry.entry_id}_1"
    )
    assert issue is not None
    assert issue.translation_key == "deprecated_zone_switch_scripts"
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["items"] == "- `automation.test`"

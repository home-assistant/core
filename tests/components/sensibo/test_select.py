"""The test for the sensibo select platform."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.sensibo.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.SELECT]],
)
async def test_select(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo select."""

    await snapshot_platform(hass, entity_registry, snapshot, load_int.entry_id)

    mock_client.async_get_devices_data.return_value.parsed[
        "AAZZAAZZ"
    ].light_mode = "dim"

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("select.kitchen_light")
    assert state.state == "dim"


async def test_select_set_option(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo select service."""

    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].active_features = [
        "timestamp",
        "on",
        "mode",
        "targetTemperature",
        "light",
    ]

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("select.kitchen_light")
    assert state.state == "on"

    mock_client.async_set_ac_state_property.return_value = {
        "result": {"status": "failed"}
    }

    with pytest.raises(
        HomeAssistantError,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_OPTION: "dim"},
            blocking=True,
        )

    state = hass.states.get("select.kitchen_light")
    assert state.state == "on"

    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].active_features = [
        "timestamp",
        "on",
        "mode",
        "targetTemperature",
        "horizontalSwing",
        "light",
    ]

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_client.async_set_ac_state_property.return_value = {
        "result": {"status": "Failed", "failureReason": "No connection"}
    }

    with pytest.raises(
        HomeAssistantError,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_OPTION: "dim"},
            blocking=True,
        )

    state = hass.states.get("select.kitchen_light")
    assert state.state == "on"

    mock_client.async_set_ac_state_property.return_value = {
        "result": {"status": "Success"}
    }

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: state.entity_id, ATTR_OPTION: "dim"},
        blocking=True,
    )

    state = hass.states.get("select.kitchen_light")
    assert state.state == "dim"


@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.SELECT]],
)
async def test_deprecated_horizontal_swing_select(
    hass: HomeAssistant,
    load_platforms: list[Platform],
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the deprecated horizontal swing select entity."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_CONFIG,
        entry_id="1",
        unique_id="firstnamelastname",
        version=2,
    )

    config_entry.add_to_hass(hass)

    entity_registry.async_get_or_create(
        SELECT_DOMAIN,
        DOMAIN,
        "ABC999111-horizontalSwing",
        config_entry=config_entry,
        disabled_by=None,
        has_entity_name=True,
        suggested_object_id="hallway_horizontal_swing",
    )

    with patch("homeassistant.components.sensibo.PLATFORMS", load_platforms):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("select.hallway_horizontal_swing")
    assert state.state == "stopped"

    # No issue created without automation or script
    assert issue_registry.issues == {}

    with (
        patch("homeassistant.components.sensibo.PLATFORMS", load_platforms),
        patch(
            # Patch check for automation, that one exist
            "homeassistant.components.sensibo.select.automations_with_entity",
            return_value=["automation.test"],
        ),
    ):
        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done(True)

    # Issue is created when entity is enabled and automation/script exist
    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_entity_horizontalswing")
    assert issue
    assert issue.translation_key == "deprecated_entity_horizontalswing"
    assert hass.states.get("select.hallway_horizontal_swing")
    assert entity_registry.async_is_registered("select.hallway_horizontal_swing")

    # Disabling the entity should remove the entity and remove the issue
    # once the integration is reloaded
    entity_registry.async_update_entity(
        state.entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )

    with (
        patch("homeassistant.components.sensibo.PLATFORMS", load_platforms),
        patch(
            "homeassistant.components.sensibo.select.automations_with_entity",
            return_value=["automation.test"],
        ),
    ):
        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done(True)

    # Disabling the entity and reloading has removed the entity and issue
    assert not hass.states.get("select.hallway_horizontal_swing")
    assert not entity_registry.async_is_registered("select.hallway_horizontal_swing")
    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_entity_horizontalswing")
    assert not issue

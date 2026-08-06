"""Test the Tewke repairs."""

from typing import Any

from pytewke.data import Scene

from homeassistant.components.tewke.const import DOMAIN
from homeassistant.components.tewke.repairs import async_create_fix_flow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry


async def test_new_scene_repair_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tap: Any,
) -> None:
    """Test the repair flow for new scenes."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Manually add a pending scene to trigger the flow
    mock_config_entry.runtime_data.pending_scenes = {
        "pending_scene_1": Scene(
            id="pending_scene_1",
            name="Pending Scene",
            created_at=123,
            device_id="device1",
            isActive=False,
            brightness=100,
        )
    }

    # Create the issue
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"new_scenes_found_{mock_config_entry.entry_id}",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="new_scenes_found",
        translation_placeholders={"name": "Tewke"},
        data={"entry_id": mock_config_entry.entry_id},
    )

    # Get the issue
    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, f"new_scenes_found_{mock_config_entry.entry_id}"
    )
    assert issue is not None

    flow = await async_create_fix_flow(hass, issue.issue_id, issue.data)
    assert flow is not None

    flow.hass = hass
    result = await flow.async_step_init()
    assert result["type"] == "form"
    assert result["step_id"] == "init"

    result = await flow.async_step_init(user_input={})
    assert result["type"] == "create_entry"
    assert result["data"] == {}

    # Issue should be deleted
    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, f"new_scenes_found_{mock_config_entry.entry_id}"
    )
    assert issue is None


async def test_no_new_scenes_abort(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tap: Any,
) -> None:
    """Test aborting the repair flow if no pending scenes are present."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_config_entry.runtime_data.pending_scenes = {}

    flow = await async_create_fix_flow(
        hass,
        f"new_scenes_found_{mock_config_entry.entry_id}",
        {"entry_id": mock_config_entry.entry_id},
    )
    assert flow is not None
    flow.hass = hass

    result = await flow.async_step_init()
    assert result["type"] == "abort"
    assert result["reason"] == "no_new_scenes"


async def test_invalid_issues(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test invalid issue handling in repair flow."""
    mock_config_entry.add_to_hass(hass)

    # Unhandled issue ID
    flow = await async_create_fix_flow(hass, "unknown_issue", {})
    assert flow is None

    # Missing data
    flow = await async_create_fix_flow(hass, "new_scenes_found_123", None)
    assert flow is None

    # Invalid entry ID type
    flow = await async_create_fix_flow(hass, "new_scenes_found_123", {"entry_id": 123})
    assert flow is None

    # Missing entry
    flow = await async_create_fix_flow(
        hass, "new_scenes_found_123", {"entry_id": "nonexistent_entry"}
    )
    assert flow is None


async def test_scene_no_longer_pending(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tap: Any,
) -> None:
    """Test the repair flow when a scene is no longer pending during apply."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Manually add pending scenes to trigger the flow
    mock_config_entry.runtime_data.pending_scenes = {
        "pending_scene_1": Scene(
            id="pending_scene_1",
            name="Pending Scene",
            created_at=123,
            device_id="device1",
            isActive=False,
            brightness=100,
        ),
        "pending_scene_2": Scene(
            id="pending_scene_2",
            name="Pending Scene 2",
            created_at=123,
            device_id="device1",
            isActive=False,
            brightness=100,
        ),
    }

    flow = await async_create_fix_flow(
        hass,
        f"new_scenes_found_{mock_config_entry.entry_id}",
        {"entry_id": mock_config_entry.entry_id},
    )
    flow.hass = hass

    # Initialize the form so `_pending_list` is populated
    await flow.async_step_init()

    # Remove one from pending before applying results, leaving the other
    del mock_config_entry.runtime_data.pending_scenes["pending_scene_1"]

    result = await flow.async_step_init(user_input={})
    assert result["type"] == "create_entry"

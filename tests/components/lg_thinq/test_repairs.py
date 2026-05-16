"""Tests for the LG ThinQ repairs."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.lg_thinq.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.repairs import (
    async_process_repairs_platforms,
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize("device_fixture", ["hood"])
async def test_deprecated_fan_speed_number_repair_flow(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_thinq_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the deprecated fan speed number entity repair flow."""
    assert await async_setup_component(hass, "repairs", {})

    # Add config entry first so we can pre-create the deprecated entity
    mock_config_entry.add_to_hass(hass)

    # Pre-create the deprecated number entity so it's found during setup
    entity_registry.async_get_or_create(
        "number",
        DOMAIN,
        "MW2-2E247F93-B570-46A6-B827-920E9E10F966_fan_speed",
        suggested_object_id="test_hood_fan_speed",
        original_name="Fan speed",
        config_entry=mock_config_entry,
    )

    with patch(
        "homeassistant.components.lg_thinq.PLATFORMS",
        [Platform.FAN, Platform.NUMBER],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "number.test_hood_fan_speed"

    # Verify the issue was created
    issue = issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id=f"deprecated_fan_speed_number_{entity_id}",
    )
    assert issue is not None
    assert issue.is_fixable is True

    # Start the repair flow
    await async_process_repairs_platforms(hass)
    client = await hass_client()
    result = await start_repair_fix_flow(
        client, DOMAIN, f"deprecated_fan_speed_number_{entity_id}"
    )

    flow_id = result["flow_id"]
    assert result["step_id"] == "confirm"

    # Submit the repair flow
    result = await process_repair_fix_flow(client, flow_id)
    assert result["type"] == "create_entry"

    # Verify the entity was disabled
    entity = entity_registry.async_get(entity_id)
    assert entity is not None
    assert entity.disabled is True
    assert entity.disabled_by is er.RegistryEntryDisabler.USER

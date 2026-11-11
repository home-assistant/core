"""Tests for the Holiday repairs."""

from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.repairs import (
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.holiday.const import DOMAIN
from homeassistant.components.holiday.repairs import async_create_fix_flow
from homeassistant.components.repairs import ConfirmRepairFlow
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


@pytest.mark.parametrize(
    ("data", "options", "issue", "steps", "expected_data", "expected_options"),
    [
        pytest.param(
            {"country": "XX"},
            {},
            "unsupported_country",
            [("country", {"country": "DE"}), ("options", {"province": "BW"})],
            {"country": "DE", "province": "BW"},
            {},
            id="country",
        ),
        pytest.param(
            {"country": "DE", "province": "XX"},
            {},
            "unsupported_province",
            [("options", {"province": "BW"})],
            {"country": "DE", "province": "BW"},
            {},
            id="province",
        ),
        pytest.param(
            {"country": "DE", "province": "BW"},
            {"categories": ["bogus"]},
            "unsupported_categories",
            [("options", {"province": "BW", "categories": ["catholic"]})],
            {"country": "DE", "province": "BW"},
            {"categories": ["catholic"]},
            id="categories",
        ),
    ],
)
async def test_unsupported_configuration_repair_flow(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    data: dict[str, str],
    options: dict[str, list[str]],
    issue: str,
    steps: list[tuple[str, dict[str, Any]]],
    expected_data: dict[str, str],
    expected_options: dict[str, list[str]],
) -> None:
    """Test fixing a configuration the holidays library no longer supports."""
    assert await async_setup_component(hass, "repairs", {})
    entry = MockConfigEntry(domain=DOMAIN, title="Test", data=data, options=options)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR

    issue_id = f"{issue}_{entry.entry_id}"
    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    for step_id, user_input in steps:
        assert result["step_id"] == step_id
        result = await process_repair_fix_flow(client, result["flow_id"], user_input)

    assert result["type"] == "create_entry"
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.data == expected_data
    assert entry.options == expected_options
    assert entry.title == "Germany, BW"
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)


async def test_repair_flow_without_entry(hass: HomeAssistant) -> None:
    """Test the fix flow of an issue whose config entry no longer exists."""
    flow = await async_create_fix_flow(
        hass,
        "unsupported_country_missing",
        {"entry_id": "missing", "issue": "unsupported_country"},
    )

    assert isinstance(flow, ConfirmRepairFlow)

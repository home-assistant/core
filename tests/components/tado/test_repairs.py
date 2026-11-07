"""Repair tests."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.tado.const import (
    CONST_OVERLAY_MANUAL,
    CONST_OVERLAY_TADO_DEFAULT,
    CONST_OVERLAY_TADO_MODE,
    DOMAIN,
    WATER_HEATER_FALLBACK_REPAIR,
)
from homeassistant.components.tado.repairs import manage_water_heater_fallback_issue
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir


def _issue_id(entry: MockConfigEntry) -> str:
    """Return the water heater fallback issue id of an entry."""
    return f"{WATER_HEATER_FALLBACK_REPAIR}_{entry.entry_id}"


@pytest.mark.parametrize(
    ("has_water_heaters", "integration_overlay_fallback"),
    [
        pytest.param(True, CONST_OVERLAY_TADO_MODE, id="tado_mode"),
        pytest.param(False, CONST_OVERLAY_TADO_DEFAULT, id="no_water_heaters"),
    ],
)
async def test_manage_water_heater_fallback_issue_not_created(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    has_water_heaters: bool,
    integration_overlay_fallback: str,
) -> None:
    """Test water heater fallback issue is not needed."""
    mock_config_entry.add_to_hass(hass)
    manage_water_heater_fallback_issue(
        hass=hass,
        entry=mock_config_entry,
        has_water_heaters=has_water_heaters,
        integration_overlay_fallback=integration_overlay_fallback,
    )
    assert not issue_registry.issues


@pytest.mark.parametrize(
    "integration_overlay_fallback", [CONST_OVERLAY_TADO_DEFAULT, CONST_OVERLAY_MANUAL]
)
async def test_manage_water_heater_fallback_issue_created(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    integration_overlay_fallback: str,
) -> None:
    """Test water heater fallback issue created cases."""
    mock_config_entry.add_to_hass(hass)
    manage_water_heater_fallback_issue(
        hass=hass,
        entry=mock_config_entry,
        has_water_heaters=True,
        integration_overlay_fallback=integration_overlay_fallback,
    )
    assert len(issue_registry.issues) == 1
    issue = issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry))
    assert issue is not None
    assert issue.config_entry_id == mock_config_entry.entry_id


@pytest.mark.parametrize(
    ("has_water_heaters", "integration_overlay_fallback"),
    [
        pytest.param(True, CONST_OVERLAY_TADO_MODE, id="tado_mode"),
        pytest.param(False, CONST_OVERLAY_TADO_DEFAULT, id="no_water_heaters"),
    ],
)
async def test_manage_water_heater_fallback_issue_deleted(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    has_water_heaters: bool,
    integration_overlay_fallback: str,
) -> None:
    """Test the issue is deleted once it no longer applies."""
    mock_config_entry.add_to_hass(hass)
    manage_water_heater_fallback_issue(
        hass=hass,
        entry=mock_config_entry,
        has_water_heaters=True,
        integration_overlay_fallback=CONST_OVERLAY_TADO_DEFAULT,
    )
    assert issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry))

    manage_water_heater_fallback_issue(
        hass=hass,
        entry=mock_config_entry,
        has_water_heaters=has_water_heaters,
        integration_overlay_fallback=integration_overlay_fallback,
    )
    assert not issue_registry.issues


async def test_manage_water_heater_fallback_issue_per_entry(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test each config entry gets and clears its own issue."""
    entry_1 = MockConfigEntry(domain=DOMAIN, unique_id="1")
    entry_2 = MockConfigEntry(domain=DOMAIN, unique_id="2")
    entry_1.add_to_hass(hass)
    entry_2.add_to_hass(hass)
    for entry in (entry_1, entry_2):
        manage_water_heater_fallback_issue(
            hass=hass,
            entry=entry,
            has_water_heaters=True,
            integration_overlay_fallback=CONST_OVERLAY_TADO_DEFAULT,
        )
    assert len(issue_registry.issues) == 2
    for entry in (entry_1, entry_2):
        issue = issue_registry.async_get_issue(DOMAIN, _issue_id(entry))
        assert issue is not None
        assert issue.config_entry_id == entry.entry_id

    manage_water_heater_fallback_issue(
        hass=hass,
        entry=entry_1,
        has_water_heaters=True,
        integration_overlay_fallback=CONST_OVERLAY_TADO_MODE,
    )
    assert issue_registry.async_get_issue(DOMAIN, _issue_id(entry_1)) is None
    assert issue_registry.async_get_issue(DOMAIN, _issue_id(entry_2)) is not None

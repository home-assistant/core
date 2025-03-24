"""Repair tests."""

import pytest

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


class MockWaterHeater:
    """Mock Water heater entity."""

    def __init__(self, zone_name) -> None:
        """Init mock entity class."""
        self.zone_name = zone_name


async def test_manage_water_heater_fallback_issue_not_created(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test water heater fallback issue is not needed."""
    zone_name = "Hot Water"
    expected_issue_id = f"{WATER_HEATER_FALLBACK_REPAIR}_{zone_name}"
    water_heater_names = [zone_name]
    manage_water_heater_fallback_issue(
        water_heater_names=water_heater_names,
        integration_overlay_fallback=CONST_OVERLAY_TADO_MODE,
        hass=hass,
    )
    assert (
        issue_registry.async_get_issue(issue_id=expected_issue_id, domain=DOMAIN)
        is None
    )


@pytest.mark.parametrize(
    "integration_overlay_fallback", [CONST_OVERLAY_TADO_DEFAULT, CONST_OVERLAY_MANUAL]
)
async def test_manage_water_heater_fallback_issue_created(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    integration_overlay_fallback: str,
) -> None:
    """Test water heater fallback issue created cases."""
    zone_name = "Hot Water"
    expected_issue_id = f"{WATER_HEATER_FALLBACK_REPAIR}_{zone_name}"
    water_heater_names = [zone_name]
    manage_water_heater_fallback_issue(
        water_heater_names=water_heater_names,
        integration_overlay_fallback=integration_overlay_fallback,
        hass=hass,
    )
    assert (
        issue_registry.async_get_issue(issue_id=expected_issue_id, domain=DOMAIN)
        is not None
    )

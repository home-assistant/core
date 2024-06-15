"""Repair tests."""

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
    water_heater_entities = [MockWaterHeater(zone_name)]
    manage_water_heater_fallback_issue(
        water_heater_entities=water_heater_entities,
        integration_overlay_fallback=CONST_OVERLAY_TADO_MODE,
        hass=hass,
    )
    assert (
        issue_registry.async_get_issue(issue_id=expected_issue_id, domain=DOMAIN)
        is None
    )


async def test_manage_water_heater_fallback_issue_created(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test water heater fallback issue created cases."""
    zone_name = "Hot Water"
    expected_issue_id = f"{WATER_HEATER_FALLBACK_REPAIR}_{zone_name}"
    water_heater_entities = [MockWaterHeater(zone_name)]
    # Case 1 when integration fallback is TADO_DEFAULT
    manage_water_heater_fallback_issue(
        water_heater_entities=water_heater_entities,
        integration_overlay_fallback=CONST_OVERLAY_TADO_DEFAULT,
        hass=hass,
    )
    assert (
        issue_registry.async_get_issue(issue_id=expected_issue_id, domain=DOMAIN)
        is not None
    )
    # Case 2 when integration fallback is MANUAL

    manage_water_heater_fallback_issue(
        water_heater_entities=water_heater_entities,
        integration_overlay_fallback=CONST_OVERLAY_MANUAL,
        hass=hass,
    )
    assert (
        issue_registry.async_get_issue(issue_id=expected_issue_id, domain=DOMAIN)
        is not None
    )

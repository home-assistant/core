"""Repair tests."""

from unittest.mock import patch

from homeassistant.components.tado.const import (
    CONST_OVERLAY_MANUAL,
    CONST_OVERLAY_TADO_DEFAULT,
    CONST_OVERLAY_TADO_MODE,
    DOMAIN,
)
from homeassistant.components.tado.repairs import manage_water_heater_fallback_issue
from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import IssueSeverity


class MockWaterHeater:
    """Mock Water heater entity."""

    def __init__(self, zone_name) -> None:
        """Init mock entity class."""
        self.zone_name = zone_name


async def test_manage_water_heater_fallback_issue_not_created(
    hass: HomeAssistant,
) -> None:
    """Test water heater fallback issue is not needed."""
    with patch(
        "homeassistant.components.tado.repairs.ir.async_create_issue"
    ) as mock_async_create_issue:
        zone_name = "Hot Water"
        water_heater_entities = [MockWaterHeater(zone_name)]
        manage_water_heater_fallback_issue(
            water_heater_entities=water_heater_entities,
            integration_overlay_fallback=CONST_OVERLAY_TADO_MODE,
            hass=hass,
        )
        mock_async_create_issue.assert_not_called()


async def test_manage_water_heater_fallback_issue_created(hass: HomeAssistant) -> None:
    """Test water heater fallback issue created cases."""
    # Case 1 when integration fallback is TADO_DEFAULT
    zone_name = "Hot Water"
    water_heater_entities = [MockWaterHeater(zone_name)]

    with patch(
        "homeassistant.components.tado.repairs.ir.async_create_issue"
    ) as mock_async_create_issue:
        manage_water_heater_fallback_issue(
            water_heater_entities=water_heater_entities,
            integration_overlay_fallback=CONST_OVERLAY_TADO_DEFAULT,
            hass=hass,
        )
        mock_async_create_issue.assert_called_once_with(
            hass=hass,
            domain=DOMAIN,
            is_fixable=False,
            is_persistent=True,
            issue_id=f"water_heater_fallback_{zone_name}",
            severity=IssueSeverity.WARNING,
            translation_key="water_heater_fallback",
        )
    # Case 2 when integration fallback is MANUAL
    with patch(
        "homeassistant.components.tado.repairs.ir.async_create_issue"
    ) as mock_async_create_issue:
        manage_water_heater_fallback_issue(
            water_heater_entities=water_heater_entities,
            integration_overlay_fallback=CONST_OVERLAY_MANUAL,
            hass=hass,
        )
        mock_async_create_issue.assert_called_once_with(
            hass=hass,
            domain=DOMAIN,
            is_fixable=False,
            is_persistent=True,
            issue_id=f"water_heater_fallback_{zone_name}",
            severity=IssueSeverity.WARNING,
            translation_key="water_heater_fallback",
        )

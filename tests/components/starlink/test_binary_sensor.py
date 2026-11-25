"""Tests Starlink binary sensors."""

from copy import deepcopy

import pytest

from homeassistant.const import STATE_OFF, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonArrayType

from . import STATUS_DATA_FIXTURE

# Alerts that a dish which does not support roaming stops reporting. The
# library builds the alert dict from the fields the dish actually sends, so
# these keys are simply absent instead of being False.
MISSING_ALERTS = (
    "alert_roaming",
    "alert_unexpected_location",
    "alert_is_power_save_idle",
)


def _status_without_missing_alerts() -> JsonArrayType:
    """Return status data where the dish omits the missing alerts."""
    status_data = deepcopy(STATUS_DATA_FIXTURE)
    for alert in MISSING_ALERTS:
        del status_data[2][alert]
    return status_data


def _status_with_motors_stuck() -> JsonArrayType:
    """Return status data where the dish reports stuck motors."""
    status_data = _status_without_missing_alerts()
    status_data[2]["alert_motors_stuck"] = True
    return status_data


@pytest.mark.parametrize(
    "entity_id",
    [
        "binary_sensor.starlink_roaming_mode",
        "binary_sensor.starlink_unexpected_location",
        "binary_sensor.starlink_sleep",
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_alert_reported_by_dish(hass: HomeAssistant, entity_id: str) -> None:
    """Test that an alert the dish reports is used as the state."""
    assert hass.states.get(entity_id).state == STATE_OFF


@pytest.mark.parametrize(
    "status_data",
    [pytest.param(_status_without_missing_alerts(), id="alerts_not_reported")],
    indirect=True,
)
@pytest.mark.parametrize(
    "entity_id",
    [
        "binary_sensor.starlink_roaming_mode",
        "binary_sensor.starlink_unexpected_location",
        "binary_sensor.starlink_sleep",
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_alert_not_reported_by_dish(hass: HomeAssistant, entity_id: str) -> None:
    """Test that an alert the dish omits is unknown instead of raising."""
    assert hass.states.get(entity_id).state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "status_data",
    [pytest.param(_status_with_motors_stuck(), id="motors_stuck")],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_remaining_alerts_unaffected(hass: HomeAssistant) -> None:
    """Test that alerts the dish still reports keep working."""
    assert hass.states.get("binary_sensor.starlink_motors_stuck").state == "on"
    assert hass.states.get("binary_sensor.starlink_thermal_throttle").state == STATE_OFF

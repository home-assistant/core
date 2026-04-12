"""Test Environment Canada sensors."""

import copy
from typing import Any

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import init_integration


async def test_alert_sensor_single_alert(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    ec_data: dict[str, Any],
) -> None:
    """Test combined alert sensor state when exactly one alert is active."""
    local_ec_data = copy.deepcopy(ec_data)
    local_ec_data["alerts"]["warnings"]["value"] = []
    await init_integration(hass, local_ec_data)

    state = hass.states.get("sensor.home_alerts")
    assert state is not None
    assert state.state == "1"
    assert state.attributes == snapshot


async def test_alert_sensor_multiple_alerts(
    hass: HomeAssistant,
    ec_data: dict[str, Any],
) -> None:
    """Test combined alert sensor shows count when multiple alerts are active."""
    await init_integration(hass, ec_data)

    state = hass.states.get("sensor.home_alerts")
    assert state is not None
    assert state.state == "2"


async def test_alert_sensor_no_alerts(
    hass: HomeAssistant,
    ec_data: dict[str, Any],
) -> None:
    """Test combined alert sensor shows 0 and no extra attributes when no alerts are active."""
    local_ec_data = copy.deepcopy(ec_data)
    for category in ("advisories", "endings", "statements", "warnings", "watches"):
        local_ec_data["alerts"][category]["value"] = []
    await init_integration(hass, local_ec_data)

    state = hass.states.get("sensor.home_alerts")
    assert state is not None
    assert state.state == "0"
    assert "alerts" not in state.attributes


async def test_alert_sensor_xml_fallback_fields(
    hass: HomeAssistant,
    ec_data: dict[str, Any],
) -> None:
    """Test that WFS-only fields absent in XML responses are omitted from attributes.

    The XML path populates only a subset of fields (title, date, alertColourLevel,
    expiryTime, url) and omits WFS-only fields such as text, area, status, etc.
    """
    local_ec_data = copy.deepcopy(ec_data)
    local_ec_data["alerts"]["advisories"]["value"] = []
    local_ec_data["alerts"]["warnings"]["value"] = [
        {
            "title": "Winter Storm Warning",
            "date": "2025-02-25T10:00:00+00:00",
            "alertColourLevel": "red",
            "expiryTime": "2025-02-26T06:00:00+00:00",
            "url": "https://weather.gc.ca/warnings/report_e.html?on61",
            # WFS-only fields absent (XML fallback)
        }
    ]

    await init_integration(hass, local_ec_data)

    state = hass.states.get("sensor.home_alerts")
    assert state is not None
    assert state.state == "1"

    alerts = state.attributes.get("alerts")
    assert alerts is not None
    assert len(alerts) == 1

    alert = alerts[0]
    # Fields present in XML fallback should appear
    assert alert["title"] == "Winter Storm Warning"
    assert alert["color"] == "red"
    assert alert["expiry"] == "2025-02-26T06:00:00+00:00"
    assert alert["url"] == "https://weather.gc.ca/warnings/report_e.html?on61"
    assert alert["type"] == "warning"
    # WFS-only fields should be absent (not just None)
    assert "text" not in alert
    assert "area" not in alert
    assert "status" not in alert
    assert "confidence" not in alert
    assert "impact" not in alert
    assert "alert_code" not in alert

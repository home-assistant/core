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
    """Test that None-valued fields are omitted from alert attributes.

    Simulates the XML fallback path where only title, date, and a subset of
    v0.13.0 fields are populated.
    """
    local_ec_data = copy.deepcopy(ec_data)
    local_ec_data["alerts"]["advisories"]["value"] = []
    local_ec_data["alerts"]["warnings"]["value"] = [
        {
            "title": "Winter Storm Warning",
            "date": "Tuesday February 25, 2025 at 10:00 UTC",
            "alertColourLevel": "red",
            "expiryTime": "20250226060000",
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
    assert alert["expiry"] == "20250226060000"
    assert alert["url"] == "https://weather.gc.ca/warnings/report_e.html?on61"
    assert alert["type"] == "warning"
    # WFS-only fields should be absent (not just None)
    assert "text" not in alert
    assert "area" not in alert
    assert "status" not in alert
    assert "confidence" not in alert
    assert "impact" not in alert
    assert "alert_code" not in alert

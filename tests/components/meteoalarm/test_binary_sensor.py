"""Tests for the MeteoAlarm binary sensor."""

from datetime import timedelta
from typing import Any

from homeassistant.components.meteoalarm.binary_sensor import MeteoAlertBinarySensor
from homeassistant.core import State
from homeassistant.util import dt as dt_util


class _MockMeteoAlertApi:
    """Mock MeteoAlert API."""

    def get_alert(self) -> dict[str, Any]:
        """Return a single active alert."""
        return {
            "expires": (dt_util.utcnow() + timedelta(hours=1)).isoformat(),
            "description": "valid prefix \ud83d valid suffix",
            "event": "test-event",
        }


def test_meteoalarm_alert_attributes_are_json_serializable() -> None:
    """Test alert attributes with surrogate characters are JSON serializable."""
    entity = MeteoAlertBinarySensor(_MockMeteoAlertApi(), "meteoalarm")

    entity.update()

    assert entity.is_on
    assert entity.extra_state_attributes is not None
    assert "\ud83d" not in entity.extra_state_attributes["description"]
    assert "valid prefix " in entity.extra_state_attributes["description"]
    assert " valid suffix" in entity.extra_state_attributes["description"]
    assert State(
        "binary_sensor.meteoalarm", "on", entity.extra_state_attributes
    ).json_fragment

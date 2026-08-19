"""Test the mvglive sensor platform."""

from unittest.mock import AsyncMock

from homeassistant.components.mvglive.sensor import PLATFORM_SCHEMA
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


def test_platform_schema_accepts_deprecated_directions() -> None:
    """Test that a legacy `directions` key still validates so the YAML can be imported.

    `directions` was deprecated in the old platform-only setup; existing
    users may still have it in `configuration.yaml`. It must not cause
    schema validation to fail, or the automatic YAML-to-config-entry import
    would break for them.
    """
    PLATFORM_SCHEMA(
        {
            "platform": "mvglive",
            "nextdeparture": [{"station": "Hauptbahnhof", "directions": "Feldmoching"}],
        }
    )


async def test_sensor_created(
    hass: HomeAssistant, config_entry: MockConfigEntry, mvg_api: dict[str, AsyncMock]
) -> None:
    """Test that the departures sensor is created and polls departures."""
    await setup_integration(hass, config_entry)

    state = hass.states.get("sensor.hauptbahnhof")
    assert state is not None
    assert int(state.state) > 0
    mvg_api["departures_async"].assert_called_once()

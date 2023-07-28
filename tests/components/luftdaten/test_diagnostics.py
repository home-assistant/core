"""Tests for the diagnostics data provided by the Sensor.Community integration."""

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    ) == {
        "P1": 8.5,
        "P2": 4.07,
        "altitude": 123.456,
        "humidity": 34.7,
        "latitude": REDACTED,
        "longitude": REDACTED,
        "pressure": 98545.0,
        "pressure_at_sealevel": 103102.13,
        "sensor_id": REDACTED,
        "temperature": 22.3,
    }

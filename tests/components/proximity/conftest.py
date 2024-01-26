"""Config test for proximity."""
import pytest

from homeassistant.core import HomeAssistant


@pytest.fixture
def config_zones(hass: HomeAssistant):
    """Set up zones for test."""
    hass.config.components.add("zone")
    hass.states.async_set(
        "zone.home",
        "zoning",
        {"name": "home", "latitude": 2.1, "longitude": 1.1, "radius": 10},
    )
    hass.states.async_set(
        "zone.work",
        "zoning",
        {"name": "work", "latitude": 2.3, "longitude": 1.3, "radius": 10},
    )

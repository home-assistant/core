"""Test squeezebox sensors."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from .conftest import configure_squeezebox_integration

from tests.common import MockConfigEntry


async def test_sensor(
    hass: HomeAssistant, config_entry: MockConfigEntry, lms: MagicMock
) -> None:
    """Test binary sensor states and attributes."""

    await configure_squeezebox_integration(hass, config_entry, lms)
    state = hass.states.get("sensor.fakelib_player_count")

    assert state is not None
    assert state.state == "10"

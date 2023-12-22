"""Test the Tessie weather platform."""
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .common import TEST_WEATHER, setup_platform


async def test_weather(
    hass: HomeAssistant, mock_get_weather, snapshot: SnapshotAssertion
) -> None:
    """Tests that the weather entity is correct."""

    assert len(hass.states.async_all("weather")) == 0

    await setup_platform(hass)

    assert len(hass.states.async_all("weather")) == 1

    mock_get_weather.assert_called_once()
    state = hass.states.get("weather.test")
    assert state.state == TEST_WEATHER["condition"]
    assert state == snapshot

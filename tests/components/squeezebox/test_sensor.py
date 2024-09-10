"""Test squeezebox sensors."""

from unittest.mock import patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import FAKE_QUERY_RESPONSE, setup_mocked_integration


async def test_sensor(hass: HomeAssistant) -> None:
    """Test binary sensor states and attributes."""

    # Setup component
    with (
        patch(
            "homeassistant.components.squeezebox.PLATFORMS",
            [Platform.SENSOR],
        ),
        patch(
            "homeassistant.components.squeezebox.Server.async_query",
            return_value=FAKE_QUERY_RESPONSE,
        ),
    ):
        await setup_mocked_integration(hass)
    state = hass.states.get("sensor.fakelib_player_count")

    assert state is not None
    assert state.state == "10"

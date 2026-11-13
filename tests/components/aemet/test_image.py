"""The image tests for the AEMET OpenData platform."""

from unittest.mock import patch

from aemet_opendata.exceptions import ApiError
from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.aemet.coordinator import WEATHER_UPDATE_INTERVAL
from homeassistant.core import HomeAssistant

from .util import async_init_integration, mock_api_call


async def test_aemet_create_images(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test creation of AEMET images."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    await async_init_integration(hass)

    state = hass.states.get("image.aemet_weather_radar")
    assert state is not None
    assert state.state == "2021-01-09T11:34:06.448809+00:00"


async def test_aemet_image_recovery(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test radar image discovery after a temporary API failure."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")

    # Simulate an initial radar failure.
    with patch(
        "homeassistant.components.aemet.AEMET.get_radar_map",
        side_effect=ApiError("Radar temporarily unavailable"),
    ):
        await async_init_integration(hass)

    # The image must not exist yet.
    assert hass.states.get("image.aemet_weather_radar") is None

    # Simulate recovery of the radar API.
    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=mock_api_call,
    ):
        freezer.tick(WEATHER_UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        # The radar image must now exist.
        state = hass.states.get("image.aemet_weather_radar")
        assert state is not None

        # Subsequent updates must not create duplicate entities.
        freezer.tick(WEATHER_UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("image.aemet_weather_radar_2") is None

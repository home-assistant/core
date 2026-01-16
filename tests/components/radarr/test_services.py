"""Test Radarr services."""

import pytest

from homeassistant.components.radarr.const import DOMAIN, SERVICE_GET_QUEUE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from . import create_entry, setup_integration

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_get_queue_service(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the get_queue service."""
    entry = await setup_integration(hass, aioclient_mock)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_QUEUE,
        {"entry_id": entry.entry_id},
        blocking=True,
        return_response=True,
    )

    assert "movies" in response
    assert isinstance(response["movies"], dict)
    # From the fixture, we should have 2 test movies
    assert len(response["movies"]) == 2

    # Check that images are included (using TMDB remote URLs)
    for movie_data in response["movies"].values():
        assert "images" in movie_data
        assert isinstance(movie_data["images"], dict)
        assert "poster" in movie_data["images"]
        assert movie_data["images"]["poster"].startswith(
            "https://image.tmdb.org/t/p/original/"
        )
        assert movie_data["images"]["poster"].endswith(".jpg")


async def test_get_queue_service_invalid_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test get_queue with invalid entry id."""
    # Set up at least one entry so the service gets registered
    await setup_integration(hass, aioclient_mock)

    with pytest.raises(ServiceValidationError, match="integration_not_found"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_QUEUE,
            {"entry_id": "invalid_id"},
            blocking=True,
            return_response=True,
        )


async def test_get_queue_service_entry_not_loaded(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test get_queue with entry that's not loaded."""
    # First set up one entry to register the service
    await setup_integration(hass, aioclient_mock)

    # Now create a second entry that isn't loaded
    unloaded_entry = create_entry(hass)

    with pytest.raises(ServiceValidationError, match="not_loaded"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_QUEUE,
            {"entry_id": unloaded_entry.entry_id},
            blocking=True,
            return_response=True,
        )

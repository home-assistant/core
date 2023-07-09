"""The test for the Trafikverket camera platform."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from pytrafikverket.trafikverket_camera import CameraInfo

from homeassistant.components.camera import async_get_image
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_camera(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    aioclient_mock: AiohttpClientMocker,
    get_camera: CameraInfo,
) -> None:
    """Test the Trafikverket Camera sensor."""
    state1 = hass.states.get("camera.test_location")
    assert state1.state == "idle"
    assert state1.attributes["description"] == "Test Camera for testing"
    assert state1.attributes["direction"] == "180"
    assert state1.attributes["full_size_photo"] is True
    assert state1.attributes["location"] == "Test location"
    assert state1.attributes["photo_url"] == "https://www.testurl.com/test_photo.jpg"
    assert state1.attributes["status"] == "Running"
    assert state1.attributes["type"] == "Road"

    with patch(
        "homeassistant.components.trafikverket_camera.coordinator.TrafikverketCamera.async_get_camera",
        return_value=get_camera,
    ):
        aioclient_mock.get(
            "https://www.testurl.com/test_photo.jpg?type=fullsize",
            content=b"9876543210",
        )
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=6),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("camera.test_location")
    assert state1.state == "idle"
    assert state1.attributes != {}

    assert await async_get_image(hass, "camera.test_location")

    monkeypatch.setattr(
        get_camera,
        "photourl",
        None,
    )
    aioclient_mock.get(
        "https://www.testurl.com/test_photo.jpg?type=fullsize",
        status=404,
    )

    with patch(
        "homeassistant.components.trafikverket_camera.coordinator.TrafikverketCamera.async_get_camera",
        return_value=get_camera,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=6),
        )
        await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, "camera.test_location")

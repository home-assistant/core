"""Fixtures for Trafikverket Camera integration tests."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest
from pytrafikverket.trafikverket_camera import CameraInfo

from homeassistant.components.trafikverket_camera.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(name="load_int")
async def load_integration_from_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, get_camera: CameraInfo
) -> MockConfigEntry:
    """Set up the Trafikverket Ferry integration in Home Assistant."""
    aioclient_mock.get(
        "https://www.testurl.com/test_photo.jpg?type=fullsize", content=b"0123456789"
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        entry_id="1",
        unique_id="123",
        title="Test location",
    )

    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.trafikverket_camera.coordinator.TrafikverketCamera.async_get_camera",
        return_value=get_camera,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


@pytest.fixture(name="get_camera")
def fixture_get_camera() -> CameraInfo:
    """Construct Camera Mock."""

    return CameraInfo(
        camera_name="Test_camera",
        camera_id="1234",
        active=True,
        deleted=False,
        description="Test Camera for testing",
        direction="180",
        fullsizephoto=True,
        location="Test location",
        modified=datetime(2022, 4, 4, 4, 4, 4, tzinfo=dt_util.UTC),
        phototime=datetime(2022, 4, 4, 4, 4, 4, tzinfo=dt_util.UTC),
        photourl="https://www.testurl.com/test_photo.jpg",
        status="Running",
        camera_type="Road",
    )

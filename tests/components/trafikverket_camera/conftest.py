"""Fixtures for Trafikverket Camera integration tests."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest
from pytrafikverket.models import CameraInfoModel

from homeassistant.components.trafikverket_camera.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(name="load_int")
async def load_integration_from_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_camera: CameraInfoModel,
) -> MockConfigEntry:
    """Set up the Trafikverket Camera integration in Home Assistant."""
    aioclient_mock.get(
        "https://www.testurl.com/test_photo.jpg?type=fullsize", content=b"0123456789"
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        entry_id="1",
        version=3,
        unique_id="trafikverket_camera-1234",
        title="Test Camera",
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
def fixture_get_camera() -> CameraInfoModel:
    """Construct Camera Mock."""

    return CameraInfoModel(
        camera_name="Test Camera",
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


@pytest.fixture(name="get_camera2")
def fixture_get_camera2() -> CameraInfoModel:
    """Construct Camera Mock 2."""

    return CameraInfoModel(
        camera_name="Test Camera2",
        camera_id="5678",
        active=True,
        deleted=False,
        description="Test Camera for testing2",
        direction="180",
        fullsizephoto=True,
        location="Test location2",
        modified=datetime(2022, 4, 4, 4, 4, 4, tzinfo=dt_util.UTC),
        phototime=datetime(2022, 4, 4, 4, 4, 4, tzinfo=dt_util.UTC),
        photourl="https://www.testurl.com/test_photo2.jpg",
        status="Running",
        camera_type="Road",
    )


@pytest.fixture(name="get_cameras")
def fixture_get_cameras() -> CameraInfoModel:
    """Construct Camera Mock with multiple cameras."""

    return [
        CameraInfoModel(
            camera_name="Test Camera",
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
        ),
        CameraInfoModel(
            camera_name="Test Camera2",
            camera_id="5678",
            active=True,
            deleted=False,
            description="Test Camera for testing2",
            direction="180",
            fullsizephoto=True,
            location="Test location2",
            modified=datetime(2022, 4, 4, 4, 4, 4, tzinfo=dt_util.UTC),
            phototime=datetime(2022, 4, 4, 4, 4, 4, tzinfo=dt_util.UTC),
            photourl="https://www.testurl.com/test_photo2.jpg",
            status="Running",
            camera_type="Road",
        ),
    ]


@pytest.fixture(name="get_camera_no_location")
def fixture_get_camera_no_location() -> CameraInfoModel:
    """Construct Camera Mock."""

    return CameraInfoModel(
        camera_name="Test Camera",
        camera_id="1234",
        active=True,
        deleted=False,
        description="Test Camera for testing",
        direction="180",
        fullsizephoto=True,
        location=None,
        modified=datetime(2022, 4, 4, 4, 4, 4, tzinfo=dt_util.UTC),
        phototime=datetime(2022, 4, 4, 4, 4, 4, tzinfo=dt_util.UTC),
        photourl="https://www.testurl.com/test_photo.jpg",
        status="Running",
        camera_type="Road",
    )

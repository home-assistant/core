"""The test for the Trafikverket Camera coordinator."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pytrafikverket.exceptions import (
    InvalidAuthentication,
    MultipleCamerasFound,
    NoCameraFound,
    UnknownError,
)
from pytrafikverket.models import CameraInfoModel

from homeassistant.components.trafikverket_camera.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_coordinator(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_camera: CameraInfoModel,
) -> None:
    """Test the Trafikverket Camera coordinator."""
    aioclient_mock.get(
        "https://www.testurl.com/test_photo.jpg?type=fullsize", content=b"0123456789"
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        entry_id="1",
        version=3,
        unique_id="trafikverket_camera-1234",
        title="Test Camera",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.trafikverket_camera.coordinator.TrafikverketCamera.async_get_camera",
        return_value=get_camera,
    ) as mock_data:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        mock_data.assert_called_once()
        state1 = hass.states.get("camera.test_camera")
        assert state1.state == "idle"


@pytest.mark.parametrize(
    ("sideeffect", "p_error", "entry_state"),
    [
        (
            InvalidAuthentication,
            ConfigEntryAuthFailed,
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            NoCameraFound,
            UpdateFailed,
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            MultipleCamerasFound,
            UpdateFailed,
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            UnknownError,
            UpdateFailed,
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
)
async def test_coordinator_failed_update(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_camera: CameraInfoModel,
    sideeffect: str,
    p_error: Exception,
    entry_state: str,
) -> None:
    """Test the Trafikverket Camera coordinator."""
    aioclient_mock.get(
        "https://www.testurl.com/test_photo.jpg?type=fullsize", content=b"0123456789"
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        entry_id="1",
        version=3,
        unique_id="trafikverket_camera-1234",
        title="Test Camera",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.trafikverket_camera.coordinator.TrafikverketCamera.async_get_camera",
        side_effect=sideeffect,
    ) as mock_data:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_data.assert_called_once()
    state = hass.states.get("camera.test_camera")
    assert state is None
    assert entry.state == entry_state


async def test_coordinator_failed_get_image(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_camera: CameraInfoModel,
) -> None:
    """Test the Trafikverket Camera coordinator."""
    aioclient_mock.get(
        "https://www.testurl.com/test_photo.jpg?type=fullsize", status=404
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        entry_id="1",
        version=3,
        unique_id="trafikverket_camera-1234",
        title="Test location",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.trafikverket_camera.coordinator.TrafikverketCamera.async_get_camera",
        return_value=get_camera,
    ) as mock_data:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_data.assert_called_once()
    state = hass.states.get("camera.test_camera")
    assert state is None
    assert entry.state is ConfigEntryState.SETUP_RETRY

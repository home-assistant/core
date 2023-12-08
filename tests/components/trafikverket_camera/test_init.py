"""Test for Trafikverket Ferry component Init."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest
from pytrafikverket.exceptions import UnknownError
from pytrafikverket.trafikverket_camera import CameraInfo

from homeassistant import config_entries
from homeassistant.components.trafikverket_camera import async_migrate_entry
from homeassistant.components.trafikverket_camera.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import ENTRY_CONFIG, ENTRY_CONFIG_OLD_CONFIG

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_entry(
    hass: HomeAssistant,
    get_camera: CameraInfo,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setup entry."""
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
    ) as mock_tvt_camera:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert len(mock_tvt_camera.mock_calls) == 1


async def test_unload_entry(
    hass: HomeAssistant,
    get_camera: CameraInfo,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test unload an entry."""
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
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED


async def test_migrate_entry(
    hass: HomeAssistant,
    get_camera: CameraInfo,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test migrate entry to version 2."""
    aioclient_mock.get(
        "https://www.testurl.com/test_photo.jpg?type=fullsize", content=b"0123456789"
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG_OLD_CONFIG,
        entry_id="1",
        unique_id="trafikverket_camera-Test location",
        title="Test location",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.trafikverket_camera.coordinator.TrafikverketCamera.async_get_camera",
        return_value=get_camera,
    ) as mock_tvt_camera:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert entry.version == 3
    assert entry.unique_id == "trafikverket_camera-1234"
    assert entry.data == ENTRY_CONFIG
    assert len(mock_tvt_camera.mock_calls) == 3


@pytest.mark.parametrize(
    ("version", "unique_id"),
    [
        (
            1,
            "trafikverket_camera-Test location",
        ),
        (
            2,
            "trafikverket_camera-1234",
        ),
    ],
)
async def test_migrate_entry_fails_with_error(
    hass: HomeAssistant,
    get_camera: CameraInfo,
    aioclient_mock: AiohttpClientMocker,
    version: int,
    unique_id: str,
) -> None:
    """Test migrate entry fails with api error."""
    aioclient_mock.get(
        "https://www.testurl.com/test_photo.jpg?type=fullsize", content=b"0123456789"
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG_OLD_CONFIG,
        entry_id="1",
        version=version,
        unique_id=unique_id,
        title="Test location",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.trafikverket_camera.coordinator.TrafikverketCamera.async_get_camera",
        side_effect=UnknownError,
    ) as mock_tvt_camera:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.MIGRATION_ERROR
    assert entry.version == version
    assert entry.unique_id == unique_id
    assert len(mock_tvt_camera.mock_calls) == 1


@pytest.mark.parametrize(
    ("version", "unique_id"),
    [
        (
            1,
            "trafikverket_camera-Test location",
        ),
        (
            2,
            "trafikverket_camera-1234",
        ),
    ],
)
async def test_migrate_entry_fails_no_id(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    version: int,
    unique_id: str,
) -> None:
    """Test migrate entry fails, camera returns no id."""
    aioclient_mock.get(
        "https://www.testurl.com/test_photo.jpg?type=fullsize", content=b"0123456789"
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG_OLD_CONFIG,
        entry_id="1",
        version=version,
        unique_id=unique_id,
        title="Test location",
    )
    entry.add_to_hass(hass)

    _camera = CameraInfo(
        camera_name="Test_camera",
        camera_id=None,
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

    with patch(
        "homeassistant.components.trafikverket_camera.coordinator.TrafikverketCamera.async_get_camera",
        return_value=_camera,
    ) as mock_tvt_camera:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.MIGRATION_ERROR
    assert entry.version == version
    assert entry.unique_id == unique_id
    assert len(mock_tvt_camera.mock_calls) == 1


async def test_no_migration_needed(
    hass: HomeAssistant,
    get_camera: CameraInfo,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test migrate entry fails, camera returns no id."""
    aioclient_mock.get(
        "https://www.testurl.com/test_photo.jpg?type=fullsize", content=b"0123456789"
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        version=3,
        entry_id="1234",
        unique_id="trafikverket_camera-1234",
        title="Test location",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.trafikverket_camera.coordinator.TrafikverketCamera.async_get_camera",
        return_value=get_camera,
    ):
        assert await async_migrate_entry(hass, entry) is True

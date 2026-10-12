"""Tests for the INDI Allsky image platform."""

import asyncio
from dataclasses import replace
from unittest.mock import AsyncMock, patch

from aioindiallsky import IndiAllSkyError, MediaData
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import image
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def mock_keogram_data() -> MediaData:
    """Fixture to provide sample keogram MediaData."""
    return MediaData.from_dict(
        "keogram",
        {
            "filename": "keogram_20260813.jpg",
            "dayDate": "2026-08-13 22:53:41",
            "night": True,
            "camera_id": 1,
            "id": 1,
        },
    )


@pytest.fixture
def mock_startrail_data() -> MediaData:
    """Fixture to provide sample startrail MediaData."""
    return MediaData.from_dict(
        "startrail",
        {
            "filename": "startrail_20260813.jpg",
            "dayDate": "2026-08-13 22:53:41",
            "night": True,
            "camera_id": 1,
            "id": 2,
        },
    )


@pytest.mark.usefixtures("mock_indi_allsky_client")
async def test_image_setup_and_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test standard successful setup and image entity snapshots."""
    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.IMAGE]):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


async def test_image_events_and_fetching(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_keogram_data: MediaData,
    mock_startrail_data: MediaData,
) -> None:
    """Test image entities update state and return image bytes on media events."""
    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.IMAGE]):
        await setup_integration(hass, mock_config_entry)

    mock_indi_allsky_client.fetch_image.side_effect = [
        b"\xff\xd8\xff\xe0keogram_bytes",
        b"\xff\xd8\xff\xe0startrail_bytes",
    ]

    initial_keogram_state = hass.states.get("image.indi_allsky_latest_keogram")
    assert initial_keogram_state is not None
    initial_keogram_token = initial_keogram_state.attributes.get("access_token")

    initial_startrail_state = hass.states.get("image.indi_allsky_latest_star_trail")
    assert initial_startrail_state is not None
    initial_startrail_token = initial_startrail_state.attributes.get("access_token")

    with patch("random.SystemRandom.getrandbits", side_effect=[999999999, 888888888]):
        for callback in mock_indi_allsky_client.callbacks.get("keogram_complete", []):
            callback(mock_keogram_data)
        for callback in mock_indi_allsky_client.callbacks.get("startrail_complete", []):
            callback(mock_startrail_data)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_indi_allsky_client.fetch_image.assert_any_call("latestkeogram")
    mock_indi_allsky_client.fetch_image.assert_any_call("lateststartrail")

    state = hass.states.get("image.indi_allsky_latest_keogram")
    assert state is not None
    assert state.state == "2026-08-13T22:53:41+00:00"
    assert state.attributes["access_token"] != initial_keogram_token

    img = await image.async_get_image(hass, "image.indi_allsky_latest_keogram")
    assert img.content == b"\xff\xd8\xff\xe0keogram_bytes"

    state = hass.states.get("image.indi_allsky_latest_star_trail")
    assert state is not None
    assert state.state == "2026-08-13T22:53:41+00:00"
    assert state.attributes["access_token"] != initial_startrail_token

    img = await image.async_get_image(hass, "image.indi_allsky_latest_star_trail")
    assert img.content == b"\xff\xd8\xff\xe0startrail_bytes"


async def test_image_fetch_error(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_keogram_data: MediaData,
    mock_startrail_data: MediaData,
) -> None:
    """Test handling of image fetch errors for keogram and startrail."""
    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.IMAGE]):
        await setup_integration(hass, mock_config_entry)

    mock_indi_allsky_client.fetch_image.side_effect = IndiAllSkyError("HTTP Error")

    for callback in mock_indi_allsky_client.callbacks.get("keogram_complete", []):
        callback(mock_keogram_data)
    for callback in mock_indi_allsky_client.callbacks.get("startrail_complete", []):
        callback(mock_startrail_data)
    await hass.async_block_till_done(wait_background_tasks=True)

    with pytest.raises(HomeAssistantError):
        await image.async_get_image(hass, "image.indi_allsky_latest_keogram")

    with pytest.raises(HomeAssistantError):
        await image.async_get_image(hass, "image.indi_allsky_latest_star_trail")

    # Verify recovery: later on-demand fetch succeeds and caches image in coordinator data
    initial_keogram_state = hass.states.get("image.indi_allsky_latest_keogram")
    assert initial_keogram_state is not None
    initial_keogram_token = initial_keogram_state.attributes["access_token"]

    mock_indi_allsky_client.fetch_image.side_effect = None
    mock_indi_allsky_client.fetch_image.return_value = (
        b"\xff\xd8\xff\xe0recovered_keogram"
    )

    with patch("random.SystemRandom.getrandbits", return_value=777777777):
        img = await image.async_get_image(hass, "image.indi_allsky_latest_keogram")
        assert img.content == b"\xff\xd8\xff\xe0recovered_keogram"

    coordinator = mock_config_entry.runtime_data
    assert coordinator.latest_keogram_image == b"\xff\xd8\xff\xe0recovered_keogram"
    assert coordinator.latest_keogram_updated is not None

    updated_keogram_state = hass.states.get("image.indi_allsky_latest_keogram")
    assert updated_keogram_state is not None
    assert updated_keogram_state.attributes["access_token"] != initial_keogram_token

    # Consecutive get_image uses cached coordinator image without network call
    mock_indi_allsky_client.fetch_image.reset_mock()
    img2 = await image.async_get_image(hass, "image.indi_allsky_latest_keogram")
    assert img2.content == b"\xff\xd8\xff\xe0recovered_keogram"
    mock_indi_allsky_client.fetch_image.assert_not_called()

    # Background fetch failure for the same media does not clear valid cached image
    coordinator.async_set_keogram_image(mock_keogram_data, None)
    assert coordinator.latest_keogram_image == b"\xff\xd8\xff\xe0recovered_keogram"
    coordinator.async_set_startrail_image(mock_startrail_data, None)


async def test_stale_media_fetch_ignored(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_keogram_data: MediaData,
    mock_startrail_data: MediaData,
) -> None:
    """Test that slower superseded background fetches do not overwrite newer media."""
    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.IMAGE]):
        await setup_integration(hass, mock_config_entry)

    keogram_2 = replace(mock_keogram_data, filename="keogram_2.jpg")
    startrail_2 = replace(mock_startrail_data, filename="startrail_2.jpg")

    first_keogram_fetch_started = asyncio.Event()
    unblock_first_keogram_fetch = asyncio.Event()
    second_keogram_fetch_started = asyncio.Event()
    unblock_second_keogram_fetch = asyncio.Event()
    first_startrail_fetch_started = asyncio.Event()
    unblock_first_startrail_fetch = asyncio.Event()
    second_startrail_fetch_started = asyncio.Event()
    unblock_second_startrail_fetch = asyncio.Event()

    async def _mock_fetch_image(filename: str) -> bytes:
        if filename == "latestkeogram":
            if not first_keogram_fetch_started.is_set():
                first_keogram_fetch_started.set()
                await unblock_first_keogram_fetch.wait()
                return b"stale_keogram"
            second_keogram_fetch_started.set()
            await unblock_second_keogram_fetch.wait()
            return b"new_keogram"
        if filename == "lateststartrail":
            if not first_startrail_fetch_started.is_set():
                first_startrail_fetch_started.set()
                await unblock_first_startrail_fetch.wait()
                return b"stale_startrail"
            second_startrail_fetch_started.set()
            await unblock_second_startrail_fetch.wait()
            return b"new_startrail"
        return b""

    mock_indi_allsky_client.fetch_image.side_effect = _mock_fetch_image

    keogram_callbacks = mock_indi_allsky_client.callbacks.get("keogram_complete", [])
    startrail_callbacks = mock_indi_allsky_client.callbacks.get(
        "startrail_complete", []
    )

    for cb in keogram_callbacks:
        cb(mock_keogram_data)
    for cb in startrail_callbacks:
        cb(mock_startrail_data)

    await asyncio.sleep(0)
    await first_keogram_fetch_started.wait()
    await first_startrail_fetch_started.wait()

    coordinator = mock_config_entry.runtime_data
    for cb in keogram_callbacks:
        cb(keogram_2)
    assert coordinator.latest_keogram is keogram_2
    assert coordinator.latest_keogram_image is None
    assert coordinator.latest_keogram_updated is None

    for cb in startrail_callbacks:
        cb(startrail_2)
    assert coordinator.latest_startrail is startrail_2
    assert coordinator.latest_startrail_image is None
    assert coordinator.latest_startrail_updated is None

    await asyncio.sleep(0)
    await second_keogram_fetch_started.wait()
    await second_startrail_fetch_started.wait()

    unblock_second_keogram_fetch.set()
    await asyncio.sleep(0)
    assert coordinator.latest_keogram_image == b"new_keogram"

    unblock_second_startrail_fetch.set()
    await asyncio.sleep(0)
    assert coordinator.latest_startrail_image == b"new_startrail"

    unblock_first_keogram_fetch.set()
    unblock_first_startrail_fetch.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.latest_keogram_image == b"new_keogram"
    assert coordinator.latest_startrail_image == b"new_startrail"

    img = await image.async_get_image(hass, "image.indi_allsky_latest_keogram")
    assert img.content == b"new_keogram"

    img = await image.async_get_image(hass, "image.indi_allsky_latest_star_trail")
    assert img.content == b"new_startrail"


async def test_on_demand_fetch_captures_media_identity_before_fetch(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_keogram_data: MediaData,
) -> None:
    """Test on-demand fetch does not overwrite newer media arriving mid-fetch."""
    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.IMAGE]):
        await setup_integration(hass, mock_config_entry)

    keogram_2 = replace(mock_keogram_data, filename="keogram_2.jpg")
    coordinator = mock_config_entry.runtime_data

    fetch_started = asyncio.Event()
    unblock_fetch = asyncio.Event()

    async def _mock_fetch(filename: str) -> bytes:
        fetch_started.set()
        await unblock_fetch.wait()
        return b"\xff\xd8\xff\xe0old_image_bytes"

    mock_indi_allsky_client.fetch_image.side_effect = _mock_fetch

    # Set initial media in coordinator without spawning background task
    coordinator.latest_keogram = mock_keogram_data
    coordinator.async_set_updated_data(
        replace(coordinator.data, latest_keogram=mock_keogram_data)
    )

    # Start on-demand image fetch
    fetch_task = asyncio.create_task(
        image.async_get_image(hass, "image.indi_allsky_latest_keogram")
    )
    await fetch_started.wait()

    # While on-demand fetch is suspended, a newer media event arrives
    coordinator.latest_keogram = keogram_2
    coordinator.latest_keogram_image = b"\xff\xd8\xff\xe0newer_image_bytes"
    coordinator.async_set_updated_data(
        replace(
            coordinator.data,
            latest_keogram=keogram_2,
            latest_keogram_image=b"\xff\xd8\xff\xe0newer_image_bytes",
        )
    )

    # Complete the on-demand fetch
    unblock_fetch.set()
    img = await fetch_task
    assert img.content == b"\xff\xd8\xff\xe0old_image_bytes"

    # Coordinator preserves newer media and does not overwrite it with old bytes
    assert coordinator.latest_keogram is keogram_2
    assert coordinator.latest_keogram_image == b"\xff\xd8\xff\xe0newer_image_bytes"


async def test_image_fetching_before_events(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test fetching images before any media event arrives."""
    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.IMAGE]):
        await setup_integration(hass, mock_config_entry)

    mock_indi_allsky_client.fetch_image.return_value = (
        b"\xff\xd8\xff\xe0fallback_keogram"
    )
    img = await image.async_get_image(hass, "image.indi_allsky_latest_keogram")
    assert img.content == b"\xff\xd8\xff\xe0fallback_keogram"
    mock_indi_allsky_client.fetch_image.assert_called_with("latestkeogram")

    mock_indi_allsky_client.fetch_image.return_value = (
        b"\xff\xd8\xff\xe0fallback_startrail"
    )
    img = await image.async_get_image(hass, "image.indi_allsky_latest_star_trail")
    assert img.content == b"\xff\xd8\xff\xe0fallback_startrail"
    mock_indi_allsky_client.fetch_image.assert_called_with("lateststartrail")


async def test_image_midnight_day_date_uses_fetch_time(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_keogram_data: MediaData,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test midnight day_date uses the coordinator image retrieval timestamp."""
    frozen_time = dt_util.parse_datetime("2026-08-14T03:15:00+00:00")
    assert frozen_time is not None
    freezer.move_to(frozen_time)

    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.IMAGE]):
        await setup_integration(hass, mock_config_entry)

    mock_indi_allsky_client.fetch_image.return_value = b"\xff\xd8\xff\xe0keogram_bytes"

    midnight_keogram_data = replace(mock_keogram_data, day_date="2026-08-13 00:00:00")
    for callback in mock_indi_allsky_client.callbacks.get("keogram_complete", []):
        callback(midnight_keogram_data)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("image.indi_allsky_latest_keogram")
    assert state is not None
    assert state.state == "2026-08-14T03:15:00+00:00"


async def test_image_last_updated_timezones_and_fallback(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_keogram_data: MediaData,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test image_last_updated timezone parsing and updated_fn fallback without day_date."""
    frozen_fallback_time = dt_util.parse_datetime("2026-08-14T05:20:00+00:00")
    assert frozen_fallback_time is not None
    freezer.move_to(frozen_fallback_time)

    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.IMAGE]):
        await setup_integration(hass, mock_config_entry)

    mock_indi_allsky_client.fetch_image.return_value = b"\xff\xd8\xff\xe0keogram_bytes"

    tz_keogram = replace(mock_keogram_data, day_date="2026-08-13 22:53:41+02:00")
    for callback in mock_indi_allsky_client.callbacks.get("keogram_complete", []):
        callback(tz_keogram)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("image.indi_allsky_latest_keogram")
    assert state is not None
    assert state.state == "2026-08-13T20:53:41+00:00"

    fallback_time = dt_util.parse_datetime("2026-08-14T06:30:00+00:00")
    assert fallback_time is not None
    freezer.move_to(fallback_time)

    no_date_keogram = replace(mock_keogram_data, day_date="")
    for callback in mock_indi_allsky_client.callbacks.get("keogram_complete", []):
        callback(no_date_keogram)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("image.indi_allsky_latest_keogram")
    assert state is not None
    assert state.state == "2026-08-14T06:30:00+00:00"

"""Tests for the INDI Allsky image platform."""

from unittest.mock import AsyncMock, patch

from aioindiallsky import IndiAllSkyError, MediaData
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import image
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

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

    for callback in mock_indi_allsky_client.callbacks.get("keogram_complete", []):
        callback(mock_keogram_data)
    for callback in mock_indi_allsky_client.callbacks.get("startrail_complete", []):
        callback(mock_startrail_data)
    await hass.async_block_till_done()

    state = hass.states.get("image.indi_allsky_latest_keogram")
    assert state is not None
    assert state.state == "2026-08-13T22:53:41+00:00"

    mock_indi_allsky_client.fetch_image.return_value = b"\xff\xd8\xff\xe0keogram_bytes"
    img = await image.async_get_image(hass, "image.indi_allsky_latest_keogram")
    assert img.content == b"\xff\xd8\xff\xe0keogram_bytes"
    mock_indi_allsky_client.fetch_image.assert_called_with("keogram_20260813.jpg")

    state = hass.states.get("image.indi_allsky_latest_star_trail")
    assert state is not None
    assert state.state == "2026-08-13T22:53:41+00:00"

    mock_indi_allsky_client.fetch_image.return_value = (
        b"\xff\xd8\xff\xe0startrail_bytes"
    )
    img = await image.async_get_image(hass, "image.indi_allsky_latest_star_trail")
    assert img.content == b"\xff\xd8\xff\xe0startrail_bytes"
    mock_indi_allsky_client.fetch_image.assert_called_with("startrail_20260813.jpg")


async def test_image_fetch_error(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_keogram_data: MediaData,
) -> None:
    """Test handling of image fetch errors."""
    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.IMAGE]):
        await setup_integration(hass, mock_config_entry)

    for callback in mock_indi_allsky_client.callbacks.get("keogram_complete", []):
        callback(mock_keogram_data)
    await hass.async_block_till_done()

    mock_indi_allsky_client.fetch_image.side_effect = IndiAllSkyError("HTTP Error")

    with pytest.raises(HomeAssistantError):
        await image.async_get_image(hass, "image.indi_allsky_latest_keogram")


async def test_image_fallback_fetching_before_events(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test fetching fallback alias images before any media event arrives."""
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

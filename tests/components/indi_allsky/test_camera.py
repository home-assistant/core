"""Tests for the INDI Allsky camera platform."""

from unittest.mock import AsyncMock

from aioindiallsky import IndiAllSkyError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.camera import async_get_image
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("mock_indi_allsky_client")
async def test_camera_setup_and_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test standard successful setup and entity snapshots using snapshot_platform."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("image_bytes", "expected_content_type"),
    [
        pytest.param(b"\xff\xd8\xff\xe0fake_jpeg_data", "image/jpeg", id="jpeg"),
        pytest.param(b"\x89PNG\r\n\x1a\nfake_png_data", "image/png", id="png"),
    ],
)
async def test_camera_image_and_update(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    image_bytes: bytes,
    expected_content_type: str,
) -> None:
    """Test camera image fetching and content type inference."""
    mock_indi_allsky_client.fetch_image.return_value = image_bytes
    await setup_integration(hass, mock_config_entry)

    image = await async_get_image(hass, "camera.indi_allsky")
    assert image.content == image_bytes
    assert image.content_type == expected_content_type


async def test_camera_image_fetch_failure(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test camera image fetching failure handling."""
    await setup_integration(hass, mock_config_entry)

    mock_indi_allsky_client.fetch_image.side_effect = IndiAllSkyError("Fetch error")

    with pytest.raises(HomeAssistantError, match="Unable to get image"):
        await async_get_image(hass, "camera.indi_allsky")

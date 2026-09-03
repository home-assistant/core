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


async def test_camera_image_and_update(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test camera image fetching and failure state."""
    await setup_integration(hass, mock_config_entry)

    image = await async_get_image(hass, "camera.indi_allsky")
    assert image.content == b"fake_jpeg_data"

    mock_indi_allsky_client.fetch_image.side_effect = IndiAllSkyError("Fetch error")

    with pytest.raises(HomeAssistantError, match="Unable to get image"):
        await async_get_image(hass, "camera.indi_allsky")

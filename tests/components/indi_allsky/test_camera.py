"""Tests for the INDI Allsky camera platform."""

from unittest.mock import AsyncMock, patch

from aioindiallsky import ExposureData, IndiAllSkyError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.camera import async_get_image
from homeassistant.const import Platform
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
    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.CAMERA]):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


async def test_camera_image_and_update(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test camera image fetching and failure state."""
    await setup_integration(hass, mock_config_entry)

    image = await async_get_image(hass, "camera.indi_allsky_camera")
    assert image.content == b"fake_jpeg_data"

    mock_indi_allsky_client.fetch_image.side_effect = IndiAllSkyError("Fetch error")

    with pytest.raises(HomeAssistantError, match="Unable to get image"):
        await async_get_image(hass, "camera.indi_allsky_camera")


async def test_camera_extra_state_attributes(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_exposure_data: ExposureData,
) -> None:
    """Test extra state attributes populated from ExposureData via WebSocket callback."""
    await setup_integration(hass, mock_config_entry)

    for callback in mock_indi_allsky_client.callbacks.get("exposure_complete", []):
        callback(mock_exposure_data)
    await hass.async_block_till_done()

    state = hass.states.get("camera.indi_allsky_camera")
    assert state is not None
    assert state.attributes["binmode"] == 1
    assert state.attributes["exposure"] == 0.185
    assert state.attributes["filename"] == "test.jpg"
    assert state.attributes["gain"] == 0.0
    assert state.attributes["night"] is False
    assert state.attributes["sqm"] == 32928.83
    assert state.attributes["stars"] == 0
    assert state.attributes["temperature"] == -273.15

"""Test the Reolink camera platform."""

from unittest.mock import MagicMock, patch

import pytest
from reolink_aio.exceptions import ReolinkError

from homeassistant.components.camera import (
    CameraState,
    async_get_image,
    async_get_stream_source,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import TEST_DUO_MODEL, TEST_NVR_NAME

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


async def test_camera(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test camera entity with fluent."""
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.CAMERA]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.CAMERA}.{TEST_NVR_NAME}_fluent"
    assert hass.states.get(entity_id).state == CameraState.IDLE

    # check getting a image from the camera
    reolink_connect.get_snapshot.return_value = b"image"
    assert (await async_get_image(hass, entity_id)).content == b"image"

    reolink_connect.get_snapshot.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, entity_id)

    # check getting the stream source
    assert await async_get_stream_source(hass, entity_id) is not None

    reolink_connect.get_snapshot.reset_mock(side_effect=True)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_camera_no_stream_source(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test camera entity with no stream source."""
    reolink_connect.model = TEST_DUO_MODEL
    reolink_connect.get_stream_source.return_value = None

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.CAMERA]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.CAMERA}.{TEST_NVR_NAME}_snapshots_fluent_lens_0"
    assert hass.states.get(entity_id).state == CameraState.IDLE

"""Test the Reolink camera platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from reolink_aio.exceptions import ReolinkError

from homeassistant.components.camera import async_get_image, async_get_stream_source
from homeassistant.components.reolink import const
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_IDLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_DUO_MODEL, TEST_NVR_NAME, TEST_UID, TEST_UID_CAM

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
    assert hass.states.get(entity_id).state == STATE_IDLE

    # check getting a image from the camera
    reolink_connect.get_snapshot.return_value = b"image"
    assert (await async_get_image(hass, entity_id)).content == b"image"

    reolink_connect.get_snapshot = AsyncMock(side_effect=ReolinkError("Test error"))
    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, entity_id)

    # check getting the stream source
    assert await async_get_stream_source(hass, entity_id) is not None


async def test_camera_no_stream_source(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test camera entity with no stream source."""
    unique_id = f"{TEST_UID}_{TEST_UID_CAM}_snapshots_sub"
    entity_id = f"{Platform.CAMERA}.{TEST_NVR_NAME}_snapshots_fluent"

    # enable the snapshots camera entity
    entity_registry.async_get_or_create(
        domain=Platform.CAMERA,
        platform=const.DOMAIN,
        unique_id=unique_id,
        config_entry=config_entry,
        suggested_object_id=f"{TEST_NVR_NAME}_snapshots_fluent",
        disabled_by=None,
    )

    reolink_connect.model = TEST_DUO_MODEL
    reolink_connect.get_stream_source.return_value = None
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.CAMERA]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    assert hass.states.get(entity_id).state == STATE_IDLE

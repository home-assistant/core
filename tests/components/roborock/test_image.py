"""Test Roborock Image platform."""

import copy
from datetime import timedelta
from http import HTTPStatus
import logging
from unittest.mock import AsyncMock, patch

import pytest
from roborock import RoborockException
from roborock.data import RoborockStateCode

from homeassistant.components.roborock import DOMAIN
from homeassistant.components.roborock.const import V1_LOCAL_NOT_CLEANING_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import FakeDevice
from .mock_data import MAP_DATA, STATUS

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import ClientSessionGenerator

_LOGGER = logging.getLogger(__name__)


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.IMAGE]


async def test_floorplan_image(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    fake_devices: list[FakeDevice],
) -> None:
    """Test floor plan map image is correctly set up."""
    assert len(hass.states.async_all("image")) == 4

    assert hass.states.get("image.roborock_s7_maxv_upstairs") is not None
    # Load the image on demand
    client = await hass_client()
    resp = await client.get("/api/image_proxy/image.roborock_s7_maxv_upstairs")
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body is not None
    assert body == b"\x89PNG-001"

    # Call a second time - this time forcing it to update - and save new image
    now = dt_util.utcnow() + timedelta(minutes=61)

    # Update maps for all v1 devices
    for fake_vacuum in fake_devices:
        if fake_vacuum.v1_properties is None:
            continue
        assert fake_vacuum.v1_properties
        fake_vacuum.v1_properties.status.in_cleaning = 1
        assert fake_vacuum.v1_properties.map_content
        fake_vacuum.v1_properties.map_content.image_content = b"\x89PNG-002"

    with (
        patch(
            "homeassistant.components.roborock.coordinator.dt_util.utcnow",
            return_value=now,
        ),
    ):
        # This should call parse_map twice as the both devices are in cleaning.
        async_fire_time_changed(hass, now)
        # Refresh device in the background
        await hass.async_block_till_done()

        resp = await client.get("/api/image_proxy/image.roborock_s7_maxv_upstairs")
        assert resp.status == HTTPStatus.OK
        resp = await client.get("/api/image_proxy/image.roborock_s7_2_upstairs")
        assert resp.status == HTTPStatus.OK

        # This image has not been loaded yet since it has never been an
        # active map.
        # XXX: Load this image the first time, but not after, and revert this.
        resp = await client.get("/api/image_proxy/image.roborock_s7_maxv_downstairs")
        assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR


async def test_fail_to_save_image(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_roborock_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that we gracefully handle a oserror on saving an image."""
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Ensure that map is still working properly.
    assert hass.states.get("image.roborock_s7_maxv_upstairs") is not None
    client = await hass_client()
    resp = await client.get("/api/image_proxy/image.roborock_s7_maxv_upstairs")
    # Test that we can get the image and it correctly serialized and unserialized.
    assert resp.status == HTTPStatus.OK

    with patch(
        "homeassistant.components.roborock.roborock_storage.Path.write_bytes",
        side_effect=OSError,
    ):
        await hass.config_entries.async_unload(mock_roborock_entry.entry_id)
        assert "Unable to write map file" in caplog.text

        # Config entry is unloaded successfully
        assert mock_roborock_entry.state is ConfigEntryState.NOT_LOADED


async def test_fail_to_load_image(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that we gracefully handle failing to load an image."""
    with (
        patch(
            "homeassistant.components.roborock.roborock_storage.Path.exists",
            return_value=True,
        ),
        patch(
            "homeassistant.components.roborock.roborock_storage.Path.read_bytes",
            side_effect=OSError,
        ) as read_bytes,
    ):
        # Reload the config entry so that the map is saved in storage and entities exist.
        await hass.config_entries.async_reload(setup_entry.entry_id)
        await hass.async_block_till_done()
        assert read_bytes.call_count == 4
    assert "Unable to read map file" in caplog.text


async def test_fail_get_map_on_startup(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_roborock_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
) -> None:
    """Test that if we fail getting map on startup, we can still create the entity."""
    assert fake_vacuum.v1_properties
    fake_vacuum.v1_properties.map_content.refresh.side_effect = RoborockException
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert (
        image_entity := hass.states.get("image.roborock_s7_maxv_upstairs")
    ) is not None
    assert image_entity.state


async def test_fail_updating_image(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    fake_vacuum: FakeDevice,
) -> None:
    """Test that we handle failing getting the image after it has already been setup.."""
    client = await hass_client()

    assert fake_vacuum.v1_properties
    fake_vacuum.v1_properties.map_content.refresh.side_effect = RoborockException
    # Copy the device status so we don't override it
    fake_vacuum.v1_properties.status = copy.deepcopy(STATUS)
    fake_vacuum.v1_properties.status.in_cleaning = 1
    fake_vacuum.v1_properties.status.refresh = AsyncMock()

    now = dt_util.utcnow() + timedelta(seconds=91)
    # Update image, but get none for parse image.
    previous_state = hass.states.get("image.roborock_s7_maxv_upstairs").state
    with (
        patch(
            "homeassistant.components.roborock.coordinator.dt_util.utcnow",
            return_value=now,
        ),
    ):
        async_fire_time_changed(hass, now)
        # Refresh device in the background
        await hass.async_block_till_done()

        resp = await client.get("/api/image_proxy/image.roborock_s7_maxv_upstairs")
    # The map should load fine from the coordinator, but it should not update the
    # last_updated timestamp.
    assert resp.ok
    assert previous_state == hass.states.get("image.roborock_s7_maxv_upstairs").state


async def test_map_status_change(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    fake_vacuum: FakeDevice,
) -> None:
    """Test floor plan map image is correctly updated on status change."""
    assert len(hass.states.async_all("image")) == 4

    assert hass.states.get("image.roborock_s7_maxv_upstairs") is not None
    client = await hass_client()
    resp = await client.get("/api/image_proxy/image.roborock_s7_maxv_upstairs")
    assert resp.status == HTTPStatus.OK
    old_body = await resp.read()
    assert old_body == b"\x89PNG-001"

    _LOGGER.debug("First image fetch complete")

    # Call a second time. This interval does not directly trigger a map update, but does
    # trigger a status update which detects the state has changed and uddates the map
    now = dt_util.utcnow() + V1_LOCAL_NOT_CLEANING_INTERVAL

    assert fake_vacuum.v1_properties
    # Copy the device prop so we don't override it
    fake_vacuum.v1_properties.status = copy.deepcopy(STATUS)
    fake_vacuum.v1_properties.status.state = RoborockStateCode.returning_home
    fake_vacuum.v1_properties.status.refresh = AsyncMock()
    fake_vacuum.v1_properties.map_content.map_data = copy.deepcopy(MAP_DATA)
    fake_vacuum.v1_properties.map_content.image_content = b"\x89PNG-003"
    fake_vacuum.v1_properties.map_content.refresh = AsyncMock()

    with patch(
        "homeassistant.components.roborock.coordinator.dt_util.utcnow",
        return_value=now,
    ):
        async_fire_time_changed(hass, now)
        # Refresh device in the background
        await hass.async_block_till_done()

        resp = await client.get("/api/image_proxy/image.roborock_s7_maxv_upstairs")

        assert resp.status == HTTPStatus.OK
        body = await resp.read()
        assert body is not None
        assert body != old_body

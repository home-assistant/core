"""Test UniFi Protect views."""
# pylint: disable=protected-access
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from pyunifiprotect.data import Camera, Event, EventType
from pyunifiprotect.exceptions import NvrError

from homeassistant.components.unifiprotect.binary_sensor import MOTION_SENSORS
from homeassistant.components.unifiprotect.const import ATTR_EVENT_THUMB
from homeassistant.components.unifiprotect.entity import TOKEN_CHANGE_INTERVAL
from homeassistant.const import STATE_ON, Platform
from homeassistant.core import HomeAssistant

from .conftest import MockEntityFixture, ids_from_device_description, time_changed


@pytest.fixture(name="thumb_url")
async def thumb_url_fixture(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    mock_camera: Camera,
    now: datetime,
):
    """Fixture for a single camera for testing the binary_sensor platform."""

    # disable pydantic validation so mocking can happen
    Camera.__config__.validate_assignment = False

    camera_obj = mock_camera.copy(deep=True)
    camera_obj._api = mock_entry.api
    camera_obj.channels[0]._api = mock_entry.api
    camera_obj.channels[1]._api = mock_entry.api
    camera_obj.channels[2]._api = mock_entry.api
    camera_obj.name = "Test Camera"
    camera_obj.is_motion_detected = True

    event = Event(
        id="test_event_id",
        type=EventType.MOTION,
        start=now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=camera_obj.id,
    )
    camera_obj.last_motion_event_id = event.id

    mock_entry.api.bootstrap.reset_objects()
    mock_entry.api.bootstrap.nvr.system_info.storage.devices = []
    mock_entry.api.bootstrap.cameras = {
        camera_obj.id: camera_obj,
    }
    mock_entry.api.bootstrap.events = {event.id: event}

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    _, entity_id = ids_from_device_description(
        Platform.BINARY_SENSOR, camera_obj, MOTION_SENSORS[0]
    )

    # make sure access tokens are generated
    await time_changed(hass, 1)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_EVENT_THUMB].startswith(
        f"/api/ufp/thumbnail/test_event_id?entity_id={entity_id}&token="
    )

    yield state.attributes[ATTR_EVENT_THUMB]

    Camera.__config__.validate_assignment = True


async def test_thumbnail_view_good(
    thumb_url: str,
    hass_client_no_auth,
    mock_entry: MockEntityFixture,
):
    """Test good result from thumbnail view."""

    mock_entry.api.get_event_thumbnail = AsyncMock()

    client = await hass_client_no_auth()

    response = await client.get(thumb_url)
    assert response.status == 200

    mock_entry.api.get_event_thumbnail.assert_called_once_with(
        "test_event_id", width=None, height=None
    )


async def test_thumbnail_view_good_args(
    thumb_url: str,
    hass_client_no_auth,
    mock_entry: MockEntityFixture,
):
    """Test good result from thumbnail view."""

    mock_entry.api.get_event_thumbnail = AsyncMock()

    client = await hass_client_no_auth()

    response = await client.get(thumb_url + "&w=200&h=200")
    assert response.status == 200

    mock_entry.api.get_event_thumbnail.assert_called_once_with(
        "test_event_id", width=200, height=200
    )


async def test_thumbnail_view_bad_width(
    thumb_url: str,
    hass_client_no_auth,
    mock_entry: MockEntityFixture,
):
    """Test good result from thumbnail view."""

    mock_entry.api.get_event_thumbnail = AsyncMock()

    client = await hass_client_no_auth()

    response = await client.get(thumb_url + "&w=safds&h=200")
    assert response.status == 404

    assert not mock_entry.api.get_event_thumbnail.called


async def test_thumbnail_view_bad_height(
    thumb_url: str,
    hass_client_no_auth,
    mock_entry: MockEntityFixture,
):
    """Test good result from thumbnail view."""

    mock_entry.api.get_event_thumbnail = AsyncMock()

    client = await hass_client_no_auth()

    response = await client.get(thumb_url + "&w=200&h=asda")
    assert response.status == 404

    assert not mock_entry.api.get_event_thumbnail.called


async def test_thumbnail_view_bad_entity_id(
    thumb_url: str,
    hass_client_no_auth,
    mock_entry: MockEntityFixture,
):
    """Test good result from thumbnail view."""

    mock_entry.api.get_event_thumbnail = AsyncMock()

    client = await hass_client_no_auth()

    response = await client.get("/api/ufp/thumbnail/test_event_id?entity_id=sdfsfd")
    assert response.status == 404

    assert not mock_entry.api.get_event_thumbnail.called


async def test_thumbnail_view_bad_access_token(
    thumb_url: str,
    hass_client_no_auth,
    mock_entry: MockEntityFixture,
):
    """Test good result from thumbnail view."""

    mock_entry.api.get_event_thumbnail = AsyncMock()

    client = await hass_client_no_auth()

    thumb_url = thumb_url[:-1]

    response = await client.get(thumb_url)
    assert response.status == 401

    assert not mock_entry.api.get_event_thumbnail.called


async def test_thumbnail_view_upstream_error(
    thumb_url: str,
    hass_client_no_auth,
    mock_entry: MockEntityFixture,
):
    """Test good result from thumbnail view."""

    mock_entry.api.get_event_thumbnail = AsyncMock(side_effect=NvrError)

    client = await hass_client_no_auth()

    response = await client.get(thumb_url)
    assert response.status == 404


async def test_thumbnail_view_no_thumb(
    thumb_url: str,
    hass_client_no_auth,
    mock_entry: MockEntityFixture,
):
    """Test good result from thumbnail view."""

    mock_entry.api.get_event_thumbnail = AsyncMock(return_value=None)

    client = await hass_client_no_auth()

    response = await client.get(thumb_url)
    assert response.status == 404


async def test_thumbnail_view_expired_access_token(
    hass: HomeAssistant,
    thumb_url: str,
    hass_client_no_auth,
    mock_entry: MockEntityFixture,
):
    """Test good result from thumbnail view."""

    mock_entry.api.get_event_thumbnail = AsyncMock()

    await time_changed(hass, TOKEN_CHANGE_INTERVAL.total_seconds())
    await time_changed(hass, TOKEN_CHANGE_INTERVAL.total_seconds())

    client = await hass_client_no_auth()

    response = await client.get(thumb_url)
    assert response.status == 401

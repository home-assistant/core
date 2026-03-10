"""Test Roborock Image platform."""

import copy
from datetime import timedelta
from http import HTTPStatus
import logging
from unittest.mock import patch

import pytest
from roborock import MultiMapsList, RoborockException
from roborock.data import RoborockStateCode
from roborock.devices.traits.v1.map_content import MapContent

from homeassistant.components.roborock.const import V1_LOCAL_NOT_CLEANING_INTERVAL
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .conftest import FakeDevice, make_home_trait
from .mock_data import (
    HOME_DATA,
    MAP_DATA,
    MULTI_MAP_LIST,
    MULTI_MAP_LIST_NO_MAP_NAMES,
    ROOM_MAPPING,
    STATUS,
)

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
        resp = await client.get("/api/image_proxy/image.roborock_s7_maxv_downstairs")
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body is not None


async def test_fail_updating_image(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    fake_vacuum: FakeDevice,
) -> None:
    """Test that we handle failing getting the image after it has already been setup."""
    client = await hass_client()

    previous_state = hass.states.get("image.roborock_s7_maxv_upstairs").state

    # Refreshing the map should fail, but we should still be able to get the existing image.
    assert fake_vacuum.v1_properties
    fake_vacuum.v1_properties.home.refresh.side_effect = RoborockException
    fake_vacuum.v1_properties.status.in_cleaning = 1

    now = dt_util.utcnow() + timedelta(seconds=91)
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
    fake_vacuum.v1_properties.status.state = RoborockStateCode.returning_home
    fake_vacuum.v1_properties.home.home_map_content = {
        0: MapContent(
            image_content=b"\x89PNG-003",
            map_data=copy.deepcopy(MAP_DATA),
        )
    }

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


@pytest.mark.parametrize(
    ("multi_maps_list", "expected_entity_ids"),
    [
        (
            MULTI_MAP_LIST,
            {
                "image.roborock_s7_2_downstairs",
                "image.roborock_s7_2_upstairs",
                "image.roborock_s7_maxv_downstairs",
                "image.roborock_s7_maxv_upstairs",
            },
        ),
        (
            MULTI_MAP_LIST_NO_MAP_NAMES,
            {
                "image.roborock_s7_2_downstairs",
                "image.roborock_s7_2_upstairs",
                # Expect default names based on map flags
                "image.roborock_s7_maxv_map_0",
                "image.roborock_s7_maxv_map_1",
            },
        ),
    ],
)
async def test_image_entity_naming(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_roborock_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
    multi_maps_list: MultiMapsList,
    expected_entity_ids: set[str],
) -> None:
    """Test entity naming when no map name is set."""
    # Override one of the vacuums multi map list response based on the
    # test parameterization
    assert fake_vacuum.v1_properties
    fake_vacuum.v1_properties.home = make_home_trait(
        map_info=multi_maps_list.map_info or [],
        current_map=STATUS.current_map,
        room_mapping=ROOM_MAPPING,
        rooms=HOME_DATA.rooms,
    )

    # Setup the config entry
    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the image entities are created with the expected names
    assert {
        state.entity_id for state in hass.states.async_all("image")
    } == expected_entity_ids

"""Test Roborock Image platform."""

from __future__ import annotations

import copy
import io
from datetime import timedelta
from http import HTTPStatus
import logging
from unittest.mock import patch

import pytest
from PIL import Image
from roborock import MultiMapsList, RoborockException
from roborock.data import RoborockStateCode
from roborock.devices.traits.v1.map_content import MapContent

from homeassistant.components.roborock.const import (
    CONF_MAP_ROTATION,
    V1_LOCAL_NOT_CLEANING_INTERVAL,
)
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


def _png_bytes(width: int, height: int) -> bytes:
    img = Image.new("RGB", (width, height))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


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

    client = await hass_client()
    resp = await client.get("/api/image_proxy/image.roborock_s7_maxv_upstairs")
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body is not None
    assert body == b"\x89PNG-001"

    now = dt_util.utcnow() + timedelta(minutes=61)

    for fake_vacuum in fake_devices:
        if fake_vacuum.v1_properties is None:
            continue
        fake_vacuum.v1_properties.status.in_cleaning = 1
        fake_vacuum.v1_properties.map_content.image_content = b"\x89PNG-002"

    with patch(
        "homeassistant.components.roborock.coordinator.dt_util.utcnow",
        return_value=now,
    ):
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()

        resp = await client.get("/api/image_proxy/image.roborock_s7_maxv_upstairs")
        assert resp.status == HTTPStatus.OK


async def test_floorplan_image_rotation(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    fake_vacuum: FakeDevice,
) -> None:
    """Test map rotation option rotates the served image."""
    setup_entry.options = {CONF_MAP_ROTATION: 90}

    assert fake_vacuum.v1_properties
    fake_vacuum.v1_properties.map_content.image_content = _png_bytes(10, 20)

    client = await hass_client()
    resp = await client.get("/api/image_proxy/image.roborock_s7_maxv_upstairs")
    assert resp.status == HTTPStatus.OK

    body = await resp.read()
    rotated = Image.open(io.BytesIO(body))
    assert rotated.size == (20, 10)


async def test_fail_updating_image(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    fake_vacuum: FakeDevice,
) -> None:
    """Test that we handle failing getting the image after it has already been setup."""
    client = await hass_client()

    previous_state = hass.states.get("image.roborock_s7_maxv_upstairs").state

    fake_vacuum.v1_properties.home.refresh.side_effect = RoborockException
    fake_vacuum.v1_properties.status.in_cleaning = 1

    now = dt_util.utcnow() + timedelta(seconds=91)
    with patch(
        "homeassistant.components.roborock.coordinator.dt_util.utcnow",
        return_value=now,
    ):
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()

        resp = await client.get("/api/image_proxy/image.roborock_s7_maxv_upstairs")

    assert resp.ok
    assert previous_state == hass.states.get("image.roborock_s7_maxv_upstairs").state


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
    fake_vacuum.v1_properties.home = make_home_trait(
        map_info=multi_maps_list.map_info or [],
        current_map=STATUS.current_map,
        room_mapping=ROOM_MAPPING,
        rooms=HOME_DATA.rooms,
    )

    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    assert {
        state.entity_id for state in hass.states.async_all("image")
    } == expected_entity_ids

"""Test Roborock Image platform."""

import copy
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import patch

from PIL import Image
import pytest
from roborock import RoborockException
from vacuum_map_parser_base.map_data import ImageConfig, ImageData

from homeassistant.components.roborock import DOMAIN
from homeassistant.components.roborock.const import V1_LOCAL_NOT_CLEANING_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .mock_data import MAP_DATA, PROP

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import ClientSessionGenerator


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.IMAGE]


async def test_floorplan_image(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
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
    assert body[0:4] == b"\x89PNG"

    # Call a second time - this time forcing it to update - and save new image
    now = dt_util.utcnow() + timedelta(minutes=61)

    # Copy the device prop so we don't override it
    prop = copy.deepcopy(PROP)
    prop.status.in_cleaning = 1
    new_map_data = copy.deepcopy(MAP_DATA)
    new_map_data.image = ImageData(
        100, 10, 10, 10, 10, ImageConfig(), Image.new("RGB", (2, 2)), lambda p: p
    )
    with (
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_prop",
            return_value=prop,
        ),
        patch(
            "homeassistant.components.roborock.coordinator.dt_util.utcnow",
            return_value=now,
        ),
        patch(
            "homeassistant.components.roborock.coordinator.RoborockMapDataParser.parse",
            return_value=MAP_DATA,
        ) as parse_map,
    ):
        # This should call parse_map twice as the both devices are in cleaning.
        async_fire_time_changed(hass, now)
        resp = await client.get("/api/image_proxy/image.roborock_s7_maxv_upstairs")
        assert resp.status == HTTPStatus.OK
        resp = await client.get("/api/image_proxy/image.roborock_s7_2_upstairs")
        assert resp.status == HTTPStatus.OK
        resp = await client.get("/api/image_proxy/image.roborock_s7_maxv_downstairs")
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body is not None

    assert parse_map.call_count == 2


async def test_floorplan_image_failed_parse(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that we correctly handle getting None from the image parser."""
    client = await hass_client()
    map_data = copy.deepcopy(MAP_DATA)
    map_data.image = None
    now = dt_util.utcnow() + timedelta(seconds=91)
    # Copy the device prop so we don't override it
    prop = copy.deepcopy(PROP)
    prop.status.in_cleaning = 1
    previous_state = hass.states.get("image.roborock_s7_maxv_upstairs").state
    # Update image, but get none for parse image.
    with (
        patch(
            "homeassistant.components.roborock.coordinator.RoborockMapDataParser.parse",
            return_value=map_data,
        ),
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_prop",
            return_value=prop,
        ),
        patch(
            "homeassistant.components.roborock.coordinator.dt_util.utcnow",
            return_value=now,
        ),
    ):
        async_fire_time_changed(hass, now)
        resp = await client.get("/api/image_proxy/image.roborock_s7_maxv_upstairs")
    # The map should load fine from the coordinator, but it should not update the
    # last_updated timestamp.
    assert resp.ok
    assert previous_state == hass.states.get("image.roborock_s7_maxv_upstairs").state


async def test_fail_to_save_image(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_roborock_entry: MockConfigEntry,
    bypass_api_fixture,
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
        patch(
            "homeassistant.components.roborock.coordinator.RoborockDataUpdateCoordinator.refresh_coordinator_map"
        ),
    ):
        # Reload the config entry so that the map is saved in storage and entities exist.
        await hass.config_entries.async_reload(setup_entry.entry_id)
        await hass.async_block_till_done()
        assert read_bytes.call_count == 4
    assert "Unable to read map file" in caplog.text


async def test_fail_parse_on_startup(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_roborock_entry: MockConfigEntry,
    bypass_api_fixture,
) -> None:
    """Test that if we fail parsing on startup, we still create the entity."""
    map_data = copy.deepcopy(MAP_DATA)
    map_data.image = None
    with patch(
        "homeassistant.components.roborock.coordinator.RoborockMapDataParser.parse",
        return_value=map_data,
    ):
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
    assert (
        image_entity := hass.states.get("image.roborock_s7_maxv_upstairs")
    ) is not None
    assert image_entity.state


async def test_fail_get_map_on_startup(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_roborock_entry: MockConfigEntry,
    bypass_api_fixture,
) -> None:
    """Test that if we fail getting map on startup, we can still create the entity."""
    with (
        patch(
            "homeassistant.components.roborock.coordinator.RoborockMqttClientV1.get_map_v1",
            return_value=None,
        ),
    ):
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
) -> None:
    """Test that we handle failing getting the image after it has already been setup.."""
    client = await hass_client()
    map_data = copy.deepcopy(MAP_DATA)
    map_data.image = None
    now = dt_util.utcnow() + timedelta(seconds=91)
    # Copy the device prop so we don't override it
    prop = copy.deepcopy(PROP)
    prop.status.in_cleaning = 1
    # Update image, but get none for parse image.
    previous_state = hass.states.get("image.roborock_s7_maxv_upstairs").state
    with (
        patch(
            "homeassistant.components.roborock.coordinator.RoborockMapDataParser.parse",
            return_value=map_data,
        ),
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_prop",
            return_value=prop,
        ),
        patch(
            "homeassistant.components.roborock.coordinator.dt_util.utcnow",
            return_value=now,
        ),
        patch(
            "homeassistant.components.roborock.coordinator.RoborockMqttClientV1.get_map_v1",
            side_effect=RoborockException,
        ),
    ):
        async_fire_time_changed(hass, now)
        resp = await client.get("/api/image_proxy/image.roborock_s7_maxv_upstairs")
    # The map should load fine from the coordinator, but it should not update the
    # last_updated timestamp.
    assert resp.ok
    assert previous_state == hass.states.get("image.roborock_s7_maxv_upstairs").state


async def test_index_error_map(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that we handle failing getting the image after it has already been setup with a indexerror."""
    client = await hass_client()
    now = dt_util.utcnow() + timedelta(seconds=91)
    # Copy the device prop so we don't override it
    prop = copy.deepcopy(PROP)
    prop.status.in_cleaning = 1
    previous_state = hass.states.get("image.roborock_s7_maxv_upstairs").state
    # Update image, but get IndexError for image.
    with (
        patch(
            "homeassistant.components.roborock.coordinator.RoborockMapDataParser.parse",
            side_effect=IndexError,
        ),
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_prop",
            return_value=prop,
        ),
        patch(
            "homeassistant.components.roborock.coordinator.dt_util.utcnow",
            return_value=now,
        ),
    ):
        async_fire_time_changed(hass, now)
        resp = await client.get("/api/image_proxy/image.roborock_s7_maxv_upstairs")
    # The map should load fine from the coordinator, but it should not update the
    # last_updated timestamp.
    assert resp.ok
    assert previous_state == hass.states.get("image.roborock_s7_maxv_upstairs").state


async def test_map_status_change(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test floor plan map image is correctly updated on status change."""
    assert len(hass.states.async_all("image")) == 4

    assert hass.states.get("image.roborock_s7_maxv_upstairs") is not None
    client = await hass_client()
    resp = await client.get("/api/image_proxy/image.roborock_s7_maxv_upstairs")
    assert resp.status == HTTPStatus.OK
    old_body = await resp.read()
    assert old_body[0:4] == b"\x89PNG"

    # Call a second time. This interval does not directly trigger a map update, but does
    # trigger a status update which detects the state has changed and uddates the map
    now = dt_util.utcnow() + V1_LOCAL_NOT_CLEANING_INTERVAL

    # Copy the device prop so we don't override it
    prop = copy.deepcopy(PROP)
    prop.status.state_name = "testing"
    new_map_data = copy.deepcopy(MAP_DATA)
    new_map_data.image = ImageData(
        100, 10, 10, 10, 10, ImageConfig(), Image.new("RGB", (2, 2)), lambda p: p
    )
    with (
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_prop",
            return_value=prop,
        ),
        patch(
            "homeassistant.components.roborock.coordinator.dt_util.utcnow",
            return_value=now,
        ),
        patch(
            "homeassistant.components.roborock.coordinator.RoborockMapDataParser.parse",
            return_value=new_map_data,
        ),
    ):
        async_fire_time_changed(hass, now)
        resp = await client.get("/api/image_proxy/image.roborock_s7_maxv_upstairs")
        assert resp.status == HTTPStatus.OK
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body is not None
    assert body != old_body

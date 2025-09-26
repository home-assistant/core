"""Test Roborock Coordinator specific logic."""

import asyncio
import copy
from datetime import timedelta
from unittest.mock import patch

import pytest
from roborock import MultiMapsList
from roborock.exceptions import RoborockException
from vacuum_map_parser_base.config.color import SupportedColor

from homeassistant.components.roborock.const import (
    CONF_SHOW_BACKGROUND,
    DOMAIN,
    GET_MAPS_SERVICE_NAME,
    V1_CLOUD_IN_CLEANING_INTERVAL,
    V1_CLOUD_NOT_CLEANING_INTERVAL,
    V1_LOCAL_IN_CLEANING_INTERVAL,
    V1_LOCAL_NOT_CLEANING_INTERVAL,
)
from homeassistant.components.roborock.coordinator import RoborockDataUpdateCoordinator
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .mock_data import PROP

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.SENSOR, Platform.VACUUM]


@pytest.mark.parametrize(
    ("interval", "in_cleaning"),
    [
        (V1_CLOUD_IN_CLEANING_INTERVAL, 1),
        (V1_CLOUD_NOT_CLEANING_INTERVAL, 0),
    ],
)
async def test_dynamic_cloud_scan_interval(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    bypass_api_fixture_v1_only,
    interval: timedelta,
    in_cleaning: int,
) -> None:
    """Test dynamic scan interval."""
    prop = copy.deepcopy(PROP)
    prop.status.in_cleaning = in_cleaning
    with (
        # Force the system to use the cloud api.
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.ping",
            side_effect=RoborockException(),
        ),
        patch(
            "homeassistant.components.roborock.RoborockMqttClientV1.get_prop",
            return_value=prop,
        ),
    ):
        await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    assert hass.states.get("sensor.roborock_s7_maxv_battery").state == "100"
    prop = copy.deepcopy(prop)
    prop.status.battery = 20
    with patch(
        "homeassistant.components.roborock.RoborockMqttClientV1.get_prop",
        return_value=prop,
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + interval - timedelta(seconds=5)
        )
        assert hass.states.get("sensor.roborock_s7_maxv_battery").state == "100"
        async_fire_time_changed(hass, dt_util.utcnow() + interval)

    assert hass.states.get("sensor.roborock_s7_maxv_battery").state == "20"


async def test_visible_background(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    bypass_api_fixture: None,
) -> None:
    """Test that a visible background is handled correctly."""
    hass.config_entries.async_update_entry(
        mock_roborock_entry,
        options={
            CONF_SHOW_BACKGROUND: True,
        },
    )
    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()
    coordinator: RoborockDataUpdateCoordinator = mock_roborock_entry.runtime_data.v1[0]
    assert coordinator.map_parser._palette.get_color(  # pylint: disable=protected-access
        SupportedColor.MAP_OUTSIDE
    ) != (0, 0, 0, 0)


@pytest.mark.parametrize(
    ("interval", "in_cleaning"),
    [
        (V1_LOCAL_IN_CLEANING_INTERVAL, 1),
        (V1_LOCAL_NOT_CLEANING_INTERVAL, 0),
    ],
)
async def test_dynamic_local_scan_interval(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    bypass_api_fixture_v1_only,
    interval: timedelta,
    in_cleaning: int,
) -> None:
    """Test dynamic scan interval."""
    prop = copy.deepcopy(PROP)
    prop.status.in_cleaning = in_cleaning
    with (
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_prop",
            return_value=prop,
        ),
    ):
        await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    assert hass.states.get("sensor.roborock_s7_maxv_battery").state == "100"
    prop = copy.deepcopy(prop)
    prop.status.battery = 20
    with patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_prop",
        return_value=prop,
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + interval - timedelta(seconds=5)
        )
        assert hass.states.get("sensor.roborock_s7_maxv_battery").state == "100"

        async_fire_time_changed(hass, dt_util.utcnow() + interval)

    assert hass.states.get("sensor.roborock_s7_maxv_battery").state == "20"


async def test_no_maps(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    bypass_api_fixture: None,
) -> None:
    """Test that a device with no maps is handled correctly."""
    prop = copy.deepcopy(PROP)
    prop.status.map_status = 252
    with (
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_prop",
            return_value=prop,
        ),
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_multi_maps_list",
            return_value=MultiMapsList(
                max_multi_map=1, max_bak_map=1, multi_map_count=0, map_info=[]
            ),
        ),
        patch(
            "homeassistant.components.roborock.RoborockMqttClientV1.load_multi_map"
        ) as load_map,
    ):
        await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    assert load_map.call_count == 0


async def test_two_maps_in_cleaning(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    bypass_api_fixture: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that we gracefully handle having two maps but we are in cleaning."""
    prop = copy.deepcopy(PROP)
    prop.status.in_cleaning = True
    with (
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_prop",
            return_value=prop,
        ),
        patch(
            "homeassistant.components.roborock.RoborockMqttClientV1.load_multi_map"
        ) as load_map,
    ):
        await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    # We should not try to load any maps as we should just get the information for our
    # current map and move on.
    assert load_map.call_count == 0
    assert (
        "Vacuum is cleaning, not switching to other maps to fetch rooms" in caplog.text
    )


async def test_failed_load_multi_map(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    bypass_api_fixture: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that we gracefully handle one map failing to load."""
    with (
        patch(
            "homeassistant.components.roborock.RoborockMqttClientV1.load_multi_map",
            side_effect=[RoborockException(), None, None, None],
        ) as load_map,
    ):
        await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    assert "Failed to change to map 1 when refreshing maps" in caplog.text
    # We continue to try and load the next map so we we should have multiple load maps.
    # 2 for both devices, even though one for one of the devices failed.
    assert load_map.call_count == 4
    # Just to be safe since we load the maps asynchronously, lets make sure that only
    # one map out of the four didn't get called.
    responses = await asyncio.gather(
        *(
            hass.services.async_call(
                DOMAIN,
                GET_MAPS_SERVICE_NAME,
                {ATTR_ENTITY_ID: dev},
                blocking=True,
                return_response=True,
            )
            for dev in ("vacuum.roborock_s7_maxv", "vacuum.roborock_s7_2")
        )
    )
    num_no_rooms = sum(
        1
        for res in responses
        for data in res.values()
        for m in data["maps"]
        if not m["rooms"]
    )
    assert num_no_rooms == 1


async def test_failed_reset_map(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    bypass_api_fixture: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that we gracefully handle not being able to revert back to the original map."""
    with (
        patch(
            "homeassistant.components.roborock.RoborockMqttClientV1.load_multi_map",
            side_effect=[None, None, None, RoborockException()],
        ) as load_map,
    ):
        await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    assert "Failed to change back to map 0 when refreshing maps" in caplog.text
    # 2 for both devices, even though one for one of the devices failed.
    assert load_map.call_count == 4
    responses = await asyncio.gather(
        *(
            hass.services.async_call(
                DOMAIN,
                GET_MAPS_SERVICE_NAME,
                {ATTR_ENTITY_ID: dev},
                blocking=True,
                return_response=True,
            )
            for dev in ("vacuum.roborock_s7_maxv", "vacuum.roborock_s7_2")
        )
    )
    num_no_rooms = sum(
        1
        for res in responses
        for data in res.values()
        for m in data["maps"]
        if not m["rooms"]
    )
    # No maps should be missing information, as we just couldn't go back to the original.
    assert num_no_rooms == 0

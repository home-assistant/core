"""Test Roborock Coordinator specific logic."""

import copy
from datetime import timedelta
from unittest.mock import patch

import pytest
from roborock.exceptions import RoborockException
from vacuum_map_parser_base.config.color import SupportedColor

from homeassistant.components.roborock.const import (
    CONF_SHOW_BACKGROUND,
    V1_CLOUD_IN_CLEANING_INTERVAL,
    V1_CLOUD_NOT_CLEANING_INTERVAL,
    V1_LOCAL_IN_CLEANING_INTERVAL,
    V1_LOCAL_NOT_CLEANING_INTERVAL,
)
from homeassistant.components.roborock.coordinator import RoborockDataUpdateCoordinator
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .mock_data import PROP

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.SENSOR]


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

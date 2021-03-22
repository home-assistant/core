"""The tests for the Netatmo sensor platform."""
from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.netatmo import sensor
from homeassistant.components.netatmo.sensor import MODULE_TYPE_WIND
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt

from .common import TEST_TIME
from .conftest import selected_platforms

from tests.common import async_fire_time_changed


async def test_weather_sensor(hass, sensor_entry):
    """Test weather sensor setup."""
    prefix = "sensor.netatmo_mystation_"

    assert hass.states.get(f"{prefix}temperature").state == "24.6"
    assert hass.states.get(f"{prefix}humidity").state == "36"
    assert hass.states.get(f"{prefix}co2").state == "749"
    assert hass.states.get(f"{prefix}pressure").state == "1017.3"


async def test_public_weather_sensor(hass, sensor_entry):
    """Test public weather sensor setup."""
    prefix = "sensor.netatmo_home_max_"

    assert hass.states.get(f"{prefix}temperature").state == "27.4"
    assert hass.states.get(f"{prefix}humidity").state == "76"
    assert hass.states.get(f"{prefix}pressure").state == "1014.4"

    prefix = "sensor.netatmo_home_avg_"

    assert hass.states.get(f"{prefix}temperature").state == "22.7"
    assert hass.states.get(f"{prefix}humidity").state == "63.2"
    assert hass.states.get(f"{prefix}pressure").state == "1010.3"

    assert len(hass.states.async_all()) > 0
    entities_before_change = len(hass.states.async_all())

    valid_option = {
        "lat_ne": 32.91336,
        "lon_ne": -117.187429,
        "lat_sw": 32.83336,
        "lon_sw": -117.26743,
        "show_on_map": True,
        "area_name": "Home avg",
        "mode": "max",
    }

    result = await hass.config_entries.options.async_init(sensor_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"new_area": "Home avg"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=valid_option
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()
    async_fire_time_changed(
        hass,
        dt.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    assert hass.states.get(f"{prefix}temperature").state == "27.4"
    assert hass.states.get(f"{prefix}humidity").state == "76"
    assert hass.states.get(f"{prefix}pressure").state == "1014.4"

    assert len(hass.states.async_all()) == entities_before_change


@pytest.mark.parametrize(
    "strength, expected",
    [(50, "Full"), (60, "High"), (80, "Medium"), (90, "Low")],
)
async def test_process_wifi(strength, expected):
    """Test wifi strength translation."""
    assert sensor.process_wifi(strength) == expected


@pytest.mark.parametrize(
    "strength, expected",
    [(50, "Full"), (70, "High"), (80, "Medium"), (90, "Low")],
)
async def test_process_rf(strength, expected):
    """Test radio strength translation."""
    assert sensor.process_rf(strength) == expected


@pytest.mark.parametrize(
    "health, expected",
    [(4, "Unhealthy"), (3, "Poor"), (2, "Fair"), (1, "Fine"), (0, "Healthy")],
)
async def test_process_health(health, expected):
    """Test health index translation."""
    assert sensor.process_health(health) == expected


@pytest.mark.parametrize(
    "model, data, expected",
    [
        (MODULE_TYPE_WIND, 5591, "Full"),
        (MODULE_TYPE_WIND, 5181, "High"),
        (MODULE_TYPE_WIND, 4771, "Medium"),
        (MODULE_TYPE_WIND, 4361, "Low"),
        (MODULE_TYPE_WIND, 4300, "Very Low"),
    ],
)
async def test_process_battery(model, data, expected):
    """Test battery level translation."""
    assert sensor.process_battery(data, model) == expected


@pytest.mark.parametrize(
    "angle, expected",
    [
        (0, "N"),
        (40, "NE"),
        (70, "E"),
        (130, "SE"),
        (160, "S"),
        (220, "SW"),
        (250, "W"),
        (310, "NW"),
        (340, "N"),
    ],
)
async def test_process_angle(angle, expected):
    """Test wind direction translation."""
    assert sensor.process_angle(angle) == expected


@pytest.mark.parametrize(
    "angle, expected",
    [(-1, 359), (-40, 320)],
)
async def test_fix_angle(angle, expected):
    """Test wind angle fix."""
    assert sensor.fix_angle(angle) == expected


@pytest.mark.parametrize(
    "uid, name, expected",
    [
        ("12:34:56:37:11:ca-reachable", "netatmo_mystation_reachable", "True"),
        ("12:34:56:03:1b:e4-rf_status", "netatmo_mystation_yard_radio", "Full"),
        (
            "12:34:56:05:25:6e-rf_status",
            "netatmo_valley_road_rain_gauge_radio",
            "Medium",
        ),
        (
            "12:34:56:36:fc:de-rf_status_lvl",
            "netatmo_mystation_netatmooutdoor_radio_level",
            "65",
        ),
        (
            "12:34:56:37:11:ca-wifi_status_lvl",
            "netatmo_mystation_wifi_level",
            "45",
        ),
        (
            "12:34:56:37:11:ca-wifi_status",
            "netatmo_mystation_wifi_status",
            "Full",
        ),
        (
            "12:34:56:37:11:ca-temp_trend",
            "netatmo_mystation_temperature_trend",
            "stable",
        ),
        (
            "12:34:56:37:11:ca-pressure_trend",
            "netatmo_mystation_pressure_trend",
            "down",
        ),
        ("12:34:56:05:51:20-sum_rain_1", "netatmo_mystation_yard_rain_last_hour", "0"),
        ("12:34:56:05:51:20-sum_rain_24", "netatmo_mystation_yard_rain_today", "0"),
        ("12:34:56:03:1b:e4-windangle", "netatmo_mystation_garden_direction", "SW"),
        (
            "12:34:56:03:1b:e4-windangle_value",
            "netatmo_mystation_garden_angle",
            "217",
        ),
        ("12:34:56:03:1b:e4-gustangle", "mystation_garden_gust_direction", "S"),
        (
            "12:34:56:03:1b:e4-gustangle",
            "netatmo_mystation_garden_gust_direction",
            "S",
        ),
        (
            "12:34:56:03:1b:e4-gustangle_value",
            "netatmo_mystation_garden_gust_angle_value",
            "206",
        ),
        (
            "12:34:56:03:1b:e4-guststrength",
            "netatmo_mystation_garden_gust_strength",
            "9",
        ),
        (
            "12:34:56:26:68:92-health_idx",
            "netatmo_baby_bedroom_health",
            "Fine",
        ),
    ],
)
async def test_weather_sensor_enabling(hass, config_entry, uid, name, expected):
    """Test enabling of by default disabled sensors."""
    with patch("time.time", return_value=TEST_TIME), selected_platforms(["sensor"]):
        states_before = len(hass.states.async_all())
        assert hass.states.get(f"sensor.{name}") is None

        registry = er.async_get(hass)
        registry.async_get_or_create(
            "sensor",
            "netatmo",
            uid,
            suggested_object_id=name,
            disabled_by=None,
        )
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

        assert len(hass.states.async_all()) > states_before
        assert hass.states.get(f"sensor.{name}").state == expected

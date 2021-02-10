"""The tests for the Netatmo climate platform."""
from freezegun import freeze_time
import pytest

from homeassistant.components.netatmo import sensor
from homeassistant.components.netatmo.helper import NetatmoArea
from homeassistant.components.netatmo.sensor import MODULE_TYPE_WIND
from homeassistant.helpers.dispatcher import async_dispatcher_send


@freeze_time("2019-06-01")
async def test_weather_sensor(hass, sensor_entry):
    """Test ."""
    await hass.async_block_till_done()

    prefix = "sensor.netatmo_mystation_"

    assert hass.states.get(prefix + "temperature").state == "24.6"
    assert hass.states.get(prefix + "humidity").state == "36"
    assert hass.states.get(prefix + "co2").state == "749"
    assert hass.states.get(prefix + "pressure").state == "1017.3"


@freeze_time("2019-06-01")
async def test_public_weather_sensor(hass, sensor_entry):
    """Test ."""
    await hass.async_block_till_done()

    prefix = "sensor.netatmo_home_avg_"

    assert hass.states.get(prefix + "temperature").state == "22.7"
    assert hass.states.get(prefix + "humidity").state == "63.2"
    assert hass.states.get(prefix + "pressure").state == "1010.3"

    prefix = "sensor.netatmo_home_max_"

    assert hass.states.get(prefix + "temperature").state == "27.4"
    assert hass.states.get(prefix + "humidity").state == "76"
    assert hass.states.get(prefix + "pressure").state == "1014.4"

    #
    area_a = NetatmoArea(
        lat_ne=32.2345678,
        lon_ne=-117.1234567,
        lat_sw=32.1234567,
        lon_sw=-117.2345678,
        show_on_map=False,
        area_name="Home avg",
        mode="avg",
    )
    async_dispatcher_send(
        hass,
        "netatmo-config-Home avg",
        area_a,
    )
    await hass.async_block_till_done()

    #
    area_b = NetatmoArea(
        lat_ne=32.2345678,
        lon_ne=-117.1234567,
        lat_sw=32.1234567,
        lon_sw=-117.2345678,
        show_on_map=True,
        area_name="Home avg",
        mode="avg",
    )
    async_dispatcher_send(
        hass,
        "netatmo-config-Home avg",
        area_b,
    )
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "strength, expected",
    [(50, "Full"), (60, "High"), (80, "Medium"), (90, "Low")],
)
async def test_process_wifi(strength, expected):
    """Test ."""
    assert sensor.process_wifi(strength) == expected


@pytest.mark.parametrize(
    "strength, expected",
    [(50, "Full"), (70, "High"), (80, "Medium"), (90, "Low")],
)
async def test_process_rf(strength, expected):
    """Test ."""
    assert sensor.process_rf(strength) == expected


@pytest.mark.parametrize(
    "health, expected",
    [(4, "Unhealthy"), (3, "Poor"), (2, "Fair"), (1, "Fine"), (0, "Healthy")],
)
async def test_process_health(health, expected):
    """Test ."""
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
    """Test ."""
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
    """Test ."""
    assert sensor.process_angle(angle) == expected


@pytest.mark.parametrize(
    "angle, expected",
    [(-1, 359), (-40, 320)],
)
async def test_fix_angle(angle, expected):
    """Test ."""
    assert sensor.fix_angle(angle) == expected


@freeze_time("2019-06-01")
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
async def test_weather_sensor_enabled(hass, sensor_entry, uid, name, expected):
    """Test ."""
    registry = await hass.helpers.entity_registry.async_get_registry()

    registry.async_get_or_create(
        "sensor",
        "netatmo",
        uid,
        suggested_object_id=name,
        disabled_by=None,
    )

    await hass.async_block_till_done()

    assert hass.states.get("sensor." + name).state == expected

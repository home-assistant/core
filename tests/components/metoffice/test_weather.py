"""The tests for the Met Office sensor component."""
from datetime import timedelta
import json
from unittest.mock import patch

from homeassistant.components.metoffice.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.util import utcnow

from . import NewDateTime
from .const import (
    DATETIME_FORMAT,
    METOFFICE_CONFIG_KINGSLYNN,
    METOFFICE_CONFIG_WAVERTREE,
    WAVERTREE_SENSOR_RESULTS,
)

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture


@patch(
    "datapoint.Forecast.datetime.datetime",
    NewDateTime,
)
async def test_site_cannot_connect(hass, requests_mock, legacy_patchable_time):
    """Test we handle cannot connect error."""

    requests_mock.get("/public/data/val/wxfcs/all/json/sitelist/", text="")
    requests_mock.get("/public/data/val/wxfcs/all/json/354107?res=3hourly", text="")
    requests_mock.get("/public/data/val/wxfcs/all/json/354107?res=daily", text="")

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("weather.met_office_wavertree_3hourly") is None
    assert hass.states.get("weather.met_office_wavertree_daily") is None
    for sensor_id in WAVERTREE_SENSOR_RESULTS:
        sensor_name, _ = WAVERTREE_SENSOR_RESULTS[sensor_id]
        sensor = hass.states.get(f"sensor.wavertree_{sensor_name}")
        assert sensor is None


@patch(
    "datapoint.Forecast.datetime.datetime",
    NewDateTime,
)
async def test_site_cannot_update(hass, requests_mock, legacy_patchable_time):
    """Test we handle cannot connect error."""

    # all metoffice test data encapsulated in here
    mock_json = json.loads(load_fixture("metoffice.json"))
    all_sites = json.dumps(mock_json["all_sites"])
    wavertree_hourly = json.dumps(mock_json["wavertree_hourly"])
    wavertree_daily = json.dumps(mock_json["wavertree_daily"])

    requests_mock.get("/public/data/val/wxfcs/all/json/sitelist/", text=all_sites)
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/354107?res=3hourly", text=wavertree_hourly
    )
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/354107?res=daily", text=wavertree_daily
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity = hass.states.get("weather.met_office_wavertree_3_hourly")
    assert entity

    entity = hass.states.get("weather.met_office_wavertree_daily")
    assert entity

    requests_mock.get("/public/data/val/wxfcs/all/json/354107?res=3hourly", text="")
    requests_mock.get("/public/data/val/wxfcs/all/json/354107?res=daily", text="")

    future_time = utcnow() + timedelta(minutes=20)
    async_fire_time_changed(hass, future_time)
    await hass.async_block_till_done()

    entity = hass.states.get("weather.met_office_wavertree_3_hourly")
    assert entity.state == STATE_UNAVAILABLE

    entity = hass.states.get("weather.met_office_wavertree_daily")
    assert entity.state == STATE_UNAVAILABLE


@patch(
    "datapoint.Forecast.datetime.datetime",
    NewDateTime,
)
async def test_one_weather_site_running(hass, requests_mock, legacy_patchable_time):
    """Test the Met Office weather platform."""

    # all metoffice test data encapsulated in here
    mock_json = json.loads(load_fixture("metoffice.json"))
    all_sites = json.dumps(mock_json["all_sites"])
    wavertree_hourly = json.dumps(mock_json["wavertree_hourly"])
    wavertree_daily = json.dumps(mock_json["wavertree_daily"])

    requests_mock.get("/public/data/val/wxfcs/all/json/sitelist/", text=all_sites)
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/354107?res=3hourly",
        text=wavertree_hourly,
    )
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/354107?res=daily",
        text=wavertree_daily,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Wavertree 3-hourly weather platform expected results
    entity = hass.states.get("weather.met_office_wavertree_3_hourly")
    assert entity

    assert entity.state == "sunny"
    assert entity.attributes.get("temperature") == 17
    assert entity.attributes.get("wind_speed") == 9
    assert entity.attributes.get("wind_bearing") == "SSE"
    assert entity.attributes.get("visibility") == "Good - 10-20"
    assert entity.attributes.get("humidity") == 50

    # Forecasts added - just pick out 1 entry to check
    assert len(entity.attributes.get("forecast")) == 35

    assert (
        entity.attributes.get("forecast")[26]["datetime"].strftime(DATETIME_FORMAT)
        == "2020-04-28 21:00:00+0000"
    )
    assert entity.attributes.get("forecast")[26]["condition"] == "cloudy"
    assert entity.attributes.get("forecast")[26]["temperature"] == 10
    assert entity.attributes.get("forecast")[26]["wind_speed"] == 4
    assert entity.attributes.get("forecast")[26]["wind_bearing"] == "NNE"

    # Wavertree daily weather platform expected results
    entity = hass.states.get("weather.met_office_wavertree_daily")
    assert entity

    assert entity.state == "sunny"
    assert entity.attributes.get("temperature") == 19
    assert entity.attributes.get("wind_speed") == 9
    assert entity.attributes.get("wind_bearing") == "SSE"
    assert entity.attributes.get("visibility") == "Good - 10-20"
    assert entity.attributes.get("humidity") == 50

    # Also has Forecasts added - again, just pick out 1 entry to check
    assert len(entity.attributes.get("forecast")) == 8

    assert (
        entity.attributes.get("forecast")[7]["datetime"].strftime(DATETIME_FORMAT)
        == "2020-04-29 12:00:00+0000"
    )
    assert entity.attributes.get("forecast")[7]["condition"] == "rainy"
    assert entity.attributes.get("forecast")[7]["temperature"] == 13
    assert entity.attributes.get("forecast")[7]["wind_speed"] == 13
    assert entity.attributes.get("forecast")[7]["wind_bearing"] == "SE"


@patch(
    "datapoint.Forecast.datetime.datetime",
    NewDateTime,
)
async def test_two_weather_sites_running(hass, requests_mock, legacy_patchable_time):
    """Test we handle two different weather sites both running."""

    # all metoffice test data encapsulated in here
    mock_json = json.loads(load_fixture("metoffice.json"))
    all_sites = json.dumps(mock_json["all_sites"])
    wavertree_hourly = json.dumps(mock_json["wavertree_hourly"])
    wavertree_daily = json.dumps(mock_json["wavertree_daily"])
    kingslynn_hourly = json.dumps(mock_json["kingslynn_hourly"])
    kingslynn_daily = json.dumps(mock_json["kingslynn_daily"])

    requests_mock.get("/public/data/val/wxfcs/all/json/sitelist/", text=all_sites)
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/354107?res=3hourly", text=wavertree_hourly
    )
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/354107?res=daily", text=wavertree_daily
    )
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/322380?res=3hourly", text=kingslynn_hourly
    )
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/322380?res=daily", text=kingslynn_daily
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_KINGSLYNN,
    )
    entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(entry2.entry_id)
    await hass.async_block_till_done()

    # Wavertree 3-hourly weather platform expected results
    entity = hass.states.get("weather.met_office_wavertree_3_hourly")
    assert entity

    assert entity.state == "sunny"
    assert entity.attributes.get("temperature") == 17
    assert entity.attributes.get("wind_speed") == 9
    assert entity.attributes.get("wind_bearing") == "SSE"
    assert entity.attributes.get("visibility") == "Good - 10-20"
    assert entity.attributes.get("humidity") == 50

    # Forecasts added - just pick out 1 entry to check
    assert len(entity.attributes.get("forecast")) == 35

    assert (
        entity.attributes.get("forecast")[18]["datetime"].strftime(DATETIME_FORMAT)
        == "2020-04-27 21:00:00+0000"
    )
    assert entity.attributes.get("forecast")[18]["condition"] == "sunny"
    assert entity.attributes.get("forecast")[18]["temperature"] == 9
    assert entity.attributes.get("forecast")[18]["wind_speed"] == 4
    assert entity.attributes.get("forecast")[18]["wind_bearing"] == "NW"

    # Wavertree daily weather platform expected results
    entity = hass.states.get("weather.met_office_wavertree_daily")
    assert entity

    assert entity.state == "sunny"
    assert entity.attributes.get("temperature") == 19
    assert entity.attributes.get("wind_speed") == 9
    assert entity.attributes.get("wind_bearing") == "SSE"
    assert entity.attributes.get("visibility") == "Good - 10-20"
    assert entity.attributes.get("humidity") == 50

    # Also has Forecasts added - again, just pick out 1 entry to check
    assert len(entity.attributes.get("forecast")) == 8

    assert (
        entity.attributes.get("forecast")[7]["datetime"].strftime(DATETIME_FORMAT)
        == "2020-04-29 12:00:00+0000"
    )
    assert entity.attributes.get("forecast")[7]["condition"] == "rainy"
    assert entity.attributes.get("forecast")[7]["temperature"] == 13
    assert entity.attributes.get("forecast")[7]["wind_speed"] == 13
    assert entity.attributes.get("forecast")[7]["wind_bearing"] == "SE"

    # King's Lynn 3-hourly weather platform expected results
    entity = hass.states.get("weather.met_office_king_s_lynn_3_hourly")
    assert entity

    assert entity.state == "sunny"
    assert entity.attributes.get("temperature") == 14
    assert entity.attributes.get("wind_speed") == 2
    assert entity.attributes.get("wind_bearing") == "E"
    assert entity.attributes.get("visibility") == "Very Good - 20-40"
    assert entity.attributes.get("humidity") == 60

    # Also has Forecast added - just pick out 1 entry to check
    assert len(entity.attributes.get("forecast")) == 35

    assert (
        entity.attributes.get("forecast")[18]["datetime"].strftime(DATETIME_FORMAT)
        == "2020-04-27 21:00:00+0000"
    )
    assert entity.attributes.get("forecast")[18]["condition"] == "cloudy"
    assert entity.attributes.get("forecast")[18]["temperature"] == 10
    assert entity.attributes.get("forecast")[18]["wind_speed"] == 7
    assert entity.attributes.get("forecast")[18]["wind_bearing"] == "SE"

    # King's Lynn daily weather platform expected results
    entity = hass.states.get("weather.met_office_king_s_lynn_daily")
    assert entity

    assert entity.state == "cloudy"
    assert entity.attributes.get("temperature") == 9
    assert entity.attributes.get("wind_speed") == 4
    assert entity.attributes.get("wind_bearing") == "ESE"
    assert entity.attributes.get("visibility") == "Very Good - 20-40"
    assert entity.attributes.get("humidity") == 75

    # All should have Forecast added - again, just picking out 1 entry to check
    assert len(entity.attributes.get("forecast")) == 8

    assert (
        entity.attributes.get("forecast")[5]["datetime"].strftime(DATETIME_FORMAT)
        == "2020-04-28 12:00:00+0000"
    )
    assert entity.attributes.get("forecast")[5]["condition"] == "cloudy"
    assert entity.attributes.get("forecast")[5]["temperature"] == 11
    assert entity.attributes.get("forecast")[5]["wind_speed"] == 7
    assert entity.attributes.get("forecast")[5]["wind_bearing"] == "ESE"

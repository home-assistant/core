"""The tests for the Met Office sensor component."""
from datetime import datetime, timedelta, timezone
import json

from homeassistant.components.metoffice.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.util import utcnow

from .const import (
    METOFFICE_CONFIG_KINGSLYNN,
    METOFFICE_CONFIG_WAVERTREE,
    WAVERTREE_SENSOR_RESULTS,
)

from tests.async_mock import Mock, patch
from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture


@patch(
    "datapoint.Forecast.datetime.datetime",
    Mock(now=Mock(return_value=datetime(2020, 4, 25, 12, tzinfo=timezone.utc))),
)
async def test_site_cannot_connect(hass, requests_mock):
    """Test we handle cannot connect error."""

    requests_mock.get("/public/data/val/wxfcs/all/json/sitelist/", text="")
    requests_mock.get("/public/data/val/wxfcs/all/json/354107?res=3hourly", text="")

    entry = MockConfigEntry(domain=DOMAIN, data=METOFFICE_CONFIG_WAVERTREE,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("weather.met_office_wavertree") is None
    for sensor_id in WAVERTREE_SENSOR_RESULTS:
        sensor_name, sensor_value = WAVERTREE_SENSOR_RESULTS[sensor_id]
        sensor = hass.states.get(f"sensor.wavertree_{sensor_name}")
        assert sensor is None


@patch(
    "datapoint.Forecast.datetime.datetime",
    Mock(now=Mock(return_value=datetime(2020, 4, 25, 12, tzinfo=timezone.utc))),
)
async def test_site_cannot_update(hass, requests_mock):
    """Test we handle cannot connect error."""

    # all metoffice test data encapsulated in here
    mock_json = json.loads(load_fixture("metoffice.json"))
    all_sites = json.dumps(mock_json["all_sites"])
    wavertree_hourly = json.dumps(mock_json["wavertree_hourly"])

    requests_mock.get("/public/data/val/wxfcs/all/json/sitelist/", text=all_sites)
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/354107?res=3hourly", text=wavertree_hourly
    )

    entry = MockConfigEntry(domain=DOMAIN, data=METOFFICE_CONFIG_WAVERTREE,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity = hass.states.get("weather.met_office_wavertree")
    assert entity

    requests_mock.get("/public/data/val/wxfcs/all/json/354107?res=3hourly", text="")

    future_time = utcnow() + timedelta(minutes=20)
    async_fire_time_changed(hass, future_time)
    await hass.async_block_till_done()

    entity = hass.states.get("weather.met_office_wavertree")
    assert entity.state == STATE_UNAVAILABLE


@patch(
    "datapoint.Forecast.datetime.datetime",
    Mock(now=Mock(return_value=datetime(2020, 4, 25, 12, tzinfo=timezone.utc))),
)
async def test_one_weather_site_running(hass, requests_mock):
    """Test the Met Office weather platform."""

    # all metoffice test data encapsulated in here
    mock_json = json.loads(load_fixture("metoffice.json"))
    all_sites = json.dumps(mock_json["all_sites"])
    wavertree_hourly = json.dumps(mock_json["wavertree_hourly"])

    requests_mock.get("/public/data/val/wxfcs/all/json/sitelist/", text=all_sites)
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/354107?res=3hourly", text=wavertree_hourly,
    )

    entry = MockConfigEntry(domain=DOMAIN, data=METOFFICE_CONFIG_WAVERTREE,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Wavertree weather platform expected results
    entity = hass.states.get("weather.met_office_wavertree")
    assert entity

    assert entity.state == "sunny"
    assert entity.attributes.get("temperature") == 17
    assert entity.attributes.get("wind_speed") == 9
    assert entity.attributes.get("wind_bearing") == "SSE"
    assert entity.attributes.get("visibility") == "Good - 10-20"
    assert entity.attributes.get("humidity") == 50


@patch(
    "datapoint.Forecast.datetime.datetime",
    Mock(now=Mock(return_value=datetime(2020, 4, 25, 12, tzinfo=timezone.utc))),
)
async def test_two_weather_sites_running(hass, requests_mock):
    """Test we handle two different weather sites both running."""

    # all metoffice test data encapsulated in here
    mock_json = json.loads(load_fixture("metoffice.json"))
    all_sites = json.dumps(mock_json["all_sites"])
    wavertree_hourly = json.dumps(mock_json["wavertree_hourly"])
    kingslynn_hourly = json.dumps(mock_json["kingslynn_hourly"])

    requests_mock.get("/public/data/val/wxfcs/all/json/sitelist/", text=all_sites)
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/354107?res=3hourly", text=wavertree_hourly
    )
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/322380?res=3hourly", text=kingslynn_hourly
    )

    entry = MockConfigEntry(domain=DOMAIN, data=METOFFICE_CONFIG_WAVERTREE,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    entry2 = MockConfigEntry(domain=DOMAIN, data=METOFFICE_CONFIG_KINGSLYNN,)
    entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(entry2.entry_id)
    await hass.async_block_till_done()

    # Wavertree weather platform expected results
    entity = hass.states.get("weather.met_office_wavertree")
    assert entity

    assert entity.state == "sunny"
    assert entity.attributes.get("temperature") == 17
    assert entity.attributes.get("wind_speed") == 9
    assert entity.attributes.get("wind_bearing") == "SSE"
    assert entity.attributes.get("visibility") == "Good - 10-20"
    assert entity.attributes.get("humidity") == 50

    # King's Lynn weather platform expected results
    entity = hass.states.get("weather.met_office_king_s_lynn")
    assert entity

    assert entity.state == "sunny"
    assert entity.attributes.get("temperature") == 14
    assert entity.attributes.get("wind_speed") == 2
    assert entity.attributes.get("wind_bearing") == "E"
    assert entity.attributes.get("visibility") == "Very Good - 20-40"
    assert entity.attributes.get("humidity") == 60

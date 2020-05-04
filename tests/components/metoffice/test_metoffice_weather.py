"""The data tests for the Met Office weather component."""
import json
import logging

from asynctest import patch

from homeassistant.components.metoffice.const import DOMAIN

from . import MockDateTime
from .const import (
    CONFIG_KINGSLYNN_3HOURLY,
    CONFIG_KINGSLYNN_DAILY,
    CONFIG_WAVERTREE_3HOURLY,
    CONFIG_WAVERTREE_DAILY,
    DATETIME_FORMAT,
)

from tests.common import MockConfigEntry, load_fixture

_LOGGER = logging.getLogger(__name__)


@patch("datetime.datetime", MockDateTime)
async def test_one_weather_site_running_3hourly(hass, requests_mock):
    """Test the Met Office weather platform."""

    # all metoffice test data encapsulated in here
    mock_json = json.loads(load_fixture("metoffice.json"))
    all_sites = json.dumps(mock_json["all_sites"])
    wavertree_hourly = json.dumps(mock_json["wavertree_hourly"])

    from datetime import datetime, timezone  # pylint: disable=import-outside-toplevel

    MockDateTime.now = classmethod(
        lambda *args, **kwargs: datetime(2020, 4, 25, 12, tzinfo=timezone.utc)
    )

    requests_mock.get("/public/data/val/wxfcs/all/json/sitelist/", text=all_sites)
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/354107?res=3hourly", text=wavertree_hourly,
    )

    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_WAVERTREE_3HOURLY,)
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

    # Forecast added - just picking out 1 entry to check
    assert len(entity.attributes.get("forecast")) == 35

    assert (
        entity.attributes.get("forecast")[26]["datetime"].strftime(DATETIME_FORMAT)
        == "2020-04-28 21:00:00+0000"
    )
    assert entity.attributes.get("forecast")[26]["condition"] == "cloudy"
    assert entity.attributes.get("forecast")[26]["temperature"] == 10
    assert entity.attributes.get("forecast")[26]["wind_speed"] == 4
    assert entity.attributes.get("forecast")[26]["wind_bearing"] == "NNE"


@patch("datetime.datetime", MockDateTime)
async def test_two_weather_sites_running_3hourly(hass, requests_mock):
    """Test we handle two different weather sites both running."""

    from datetime import datetime, timezone  # pylint: disable=import-outside-toplevel

    MockDateTime.now = classmethod(
        lambda *args, **kwargs: datetime(2020, 4, 25, 12, tzinfo=timezone.utc)
    )

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

    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_WAVERTREE_3HOURLY,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    entry2 = MockConfigEntry(domain=DOMAIN, data=CONFIG_KINGSLYNN_3HOURLY,)
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

    # Forecast added - just picking out 1 entry to check
    assert len(entity.attributes.get("forecast")) == 35

    assert (
        entity.attributes.get("forecast")[26]["datetime"].strftime(DATETIME_FORMAT)
        == "2020-04-28 21:00:00+0000"
    )
    assert entity.attributes.get("forecast")[26]["condition"] == "cloudy"
    assert entity.attributes.get("forecast")[26]["temperature"] == 10
    assert entity.attributes.get("forecast")[26]["wind_speed"] == 4
    assert entity.attributes.get("forecast")[26]["wind_bearing"] == "NNE"

    # King's Lynn weather platform expected results
    entity = hass.states.get("weather.met_office_king_s_lynn")
    assert entity

    assert entity.state == "sunny"
    assert entity.attributes.get("temperature") == 14
    assert entity.attributes.get("wind_speed") == 2
    assert entity.attributes.get("wind_bearing") == "E"
    assert entity.attributes.get("visibility") == "Very Good - 20-40"
    assert entity.attributes.get("humidity") == 60

    # Forecast added - just picking out 1 entry to check
    assert len(entity.attributes.get("forecast")) == 35

    assert (
        entity.attributes.get("forecast")[25]["datetime"].strftime(DATETIME_FORMAT)
        == "2020-04-28 18:00:00+0000"
    )
    assert entity.attributes.get("forecast")[25]["condition"] == "cloudy"
    assert entity.attributes.get("forecast")[25]["temperature"] == 12
    assert entity.attributes.get("forecast")[25]["wind_speed"] == 7
    assert entity.attributes.get("forecast")[25]["wind_bearing"] == "SSE"


@patch("datetime.datetime", MockDateTime)
async def test_one_site_running_daily(hass, requests_mock):
    """Test the weather platform setup with daily update mode."""

    from datetime import datetime, timezone  # pylint: disable=import-outside-toplevel

    MockDateTime.now = classmethod(
        lambda *args, **kwargs: datetime(2020, 4, 25, 12, tzinfo=timezone.utc)
    )

    # all metoffice test data encapsulated in here
    mock_json = json.loads(load_fixture("metoffice.json"))
    all_sites = json.dumps(mock_json["all_sites"])
    wavertree_daily = json.dumps(mock_json["wavertree_daily"])

    requests_mock.get("/public/data/val/wxfcs/all/json/sitelist/", text=all_sites)
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/354107?res=daily", text=wavertree_daily,
    )

    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_WAVERTREE_DAILY,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity = hass.states.get("weather.met_office_wavertree")
    assert entity

    assert entity.state == "sunny"
    assert entity.attributes.get("temperature") == 19
    assert entity.attributes.get("wind_speed") == 9
    assert entity.attributes.get("wind_bearing") == "SSE"
    assert entity.attributes.get("visibility") == "Good - 10-20"
    assert entity.attributes.get("humidity") == 50

    assert len(entity.attributes.get("forecast")) == 8

    assert (
        entity.attributes.get("forecast")[7]["datetime"].strftime(DATETIME_FORMAT)
        == "2020-04-29 12:00:00+0000"
    )
    assert entity.attributes.get("forecast")[7]["condition"] == "rainy"
    assert entity.attributes.get("forecast")[7]["temperature"] == 13
    assert entity.attributes.get("forecast")[7]["wind_speed"] == 13
    assert entity.attributes.get("forecast")[7]["wind_bearing"] == "SE"


@patch("datetime.datetime", MockDateTime)
async def test_two_sites_running_3hourly_and_daily(hass, requests_mock):
    """Test the weather platform setup with daily update mode."""

    from datetime import datetime, timezone  # pylint: disable=import-outside-toplevel

    MockDateTime.now = classmethod(
        lambda *args, **kwargs: datetime(2020, 4, 25, 12, tzinfo=timezone.utc)
    )

    # all metoffice test data encapsulated in here
    mock_json = json.loads(load_fixture("metoffice.json"))
    all_sites = json.dumps(mock_json["all_sites"])
    wavertree_hourly = json.dumps(mock_json["wavertree_hourly"])
    kingslynn_daily = json.dumps(mock_json["kingslynn_daily"])

    requests_mock.get("/public/data/val/wxfcs/all/json/sitelist/", text=all_sites)
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/354107?res=3hourly", text=wavertree_hourly
    )
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/322380?res=daily", text=kingslynn_daily,
    )

    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_WAVERTREE_3HOURLY,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    entry2 = MockConfigEntry(domain=DOMAIN, data=CONFIG_KINGSLYNN_DAILY,)
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

    # Forecast added - just picking out 1 entry to check
    assert len(entity.attributes.get("forecast")) == 35

    assert (
        entity.attributes.get("forecast")[18]["datetime"].strftime(DATETIME_FORMAT)
        == "2020-04-27 21:00:00+0000"
    )
    assert entity.attributes.get("forecast")[18]["condition"] == "sunny"
    assert entity.attributes.get("forecast")[18]["temperature"] == 9
    assert entity.attributes.get("forecast")[18]["wind_speed"] == 4
    assert entity.attributes.get("forecast")[18]["wind_bearing"] == "NW"

    # King's Lynn weather platform expected results
    entity = hass.states.get("weather.met_office_king_s_lynn")
    assert entity

    assert entity.state == "cloudy"
    assert entity.attributes.get("temperature") == 9
    assert entity.attributes.get("wind_speed") == 4
    assert entity.attributes.get("wind_bearing") == "ESE"
    assert entity.attributes.get("visibility") == "Very Good - 20-40"
    assert entity.attributes.get("humidity") == 75

    # Forecast added - just picking out 1 entry to check
    assert len(entity.attributes.get("forecast")) == 8

    assert (
        entity.attributes.get("forecast")[7]["datetime"].strftime(DATETIME_FORMAT)
        == "2020-04-29 12:00:00+0000"
    )
    assert entity.attributes.get("forecast")[7]["condition"] == "cloudy"
    assert entity.attributes.get("forecast")[7]["temperature"] == 12
    assert entity.attributes.get("forecast")[7]["wind_speed"] == 11
    assert entity.attributes.get("forecast")[7]["wind_bearing"] == "SSE"


@patch("datetime.datetime", MockDateTime)
async def test_update_site_from_3hourly_to_daily(hass, requests_mock):
    """Test changing a working site from 3 hourly data to daily data."""

    from datetime import datetime, timezone  # pylint: disable=import-outside-toplevel

    MockDateTime.now = classmethod(
        lambda *args, **kwargs: datetime(2020, 4, 25, 12, tzinfo=timezone.utc)
    )

    # all metoffice test data encapsulated in here
    mock_json = json.loads(load_fixture("metoffice.json"))
    all_sites = json.dumps(mock_json["all_sites"])
    kingslynn_hourly = json.dumps(mock_json["kingslynn_hourly"])
    kingslynn_daily = json.dumps(mock_json["kingslynn_daily"])

    requests_mock.get("/public/data/val/wxfcs/all/json/sitelist/", text=all_sites)
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/322380?res=3hourly", text=kingslynn_hourly
    )
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/322380?res=daily", text=kingslynn_daily,
    )

    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_KINGSLYNN_3HOURLY,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # King's Lynn weather platform (3 hourly) expected results
    entity = hass.states.get("weather.met_office_king_s_lynn")
    assert entity

    assert entity.state == "sunny"
    assert entity.attributes.get("temperature") == 14
    assert entity.attributes.get("wind_speed") == 2
    assert entity.attributes.get("wind_bearing") == "E"
    assert entity.attributes.get("visibility") == "Very Good - 20-40"
    assert entity.attributes.get("humidity") == 60

    # Forecast added - just picking out 1 entry to check
    assert len(entity.attributes.get("forecast")) == 35

    assert (
        entity.attributes.get("forecast")[18]["datetime"].strftime(DATETIME_FORMAT)
        == "2020-04-27 21:00:00+0000"
    )
    assert entity.attributes.get("forecast")[18]["condition"] == "cloudy"
    assert entity.attributes.get("forecast")[18]["temperature"] == 10
    assert entity.attributes.get("forecast")[18]["wind_speed"] == 7
    assert entity.attributes.get("forecast")[18]["wind_bearing"] == "SE"

    # trigger the configuration update and then check the new data
    hass.config_entries.async_update_entry(
        entry=entry, options=CONFIG_KINGSLYNN_DAILY,
    )
    await hass.async_block_till_done()

    # King's Lynn weather platform (daily forecast) expected results
    entity = hass.states.get("weather.met_office_king_s_lynn")
    assert entity

    assert entity.state == "cloudy"
    assert entity.attributes.get("temperature") == 9
    assert entity.attributes.get("wind_speed") == 4
    assert entity.attributes.get("wind_bearing") == "ESE"
    assert entity.attributes.get("visibility") == "Very Good - 20-40"
    assert entity.attributes.get("humidity") == 75

    # Forecast added - just picking out 1 entry to check
    assert len(entity.attributes.get("forecast")) == 8

    assert (
        entity.attributes.get("forecast")[5]["datetime"].strftime(DATETIME_FORMAT)
        == "2020-04-28 12:00:00+0000"
    )
    assert entity.attributes.get("forecast")[5]["condition"] == "cloudy"
    assert entity.attributes.get("forecast")[5]["temperature"] == 11
    assert entity.attributes.get("forecast")[5]["wind_speed"] == 7
    assert entity.attributes.get("forecast")[5]["wind_bearing"] == "ESE"

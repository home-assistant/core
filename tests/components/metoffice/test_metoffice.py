"""The tests for the Met Office weather component."""
from datetime import datetime
import json
import logging

from asynctest import patch

from homeassistant.components.metoffice.const import ATTRIBUTION, DOMAIN

from .const import (
    DATETIME_FORMAT,
    METOFFICE_CONFIG_KINGSLYNN,
    METOFFICE_CONFIG_WAVERTREE,
    TEST_SITE_NAME_KINGSLYNN,
    TEST_SITE_NAME_WAVERTREE,
)

from tests.common import MockConfigEntry, load_fixture

_LOGGER = logging.getLogger(__name__)

KINGSLYNN_SENSOR_RESULTS = {
    "weather": ("weather", "sunny"),
    "visibility": ("visibility", "Very Good"),
    "visibility_distance": ("visibility_distance", "20-40"),
    "temperature": ("temperature", "14"),
    "feels_like_temperature": ("feels_like_temperature", "13"),
    "uv": ("uv_index", "6"),
    "precipitation": ("probability_of_precipitation", "0"),
    "wind_direction": ("wind_direction", "E"),
    "wind_gust": ("wind_gust", "7"),
    "wind_speed": ("wind_speed", "2"),
    "humidity": ("humidity", "60"),
}

WAVERTREE_SENSOR_RESULTS = {
    "weather": ("weather", "sunny"),
    "visibility": ("visibility", "Good"),
    "visibility_distance": ("visibility_distance", "10-20"),
    "temperature": ("temperature", "17"),
    "feels_like_temperature": ("feels_like_temperature", "14"),
    "uv": ("uv_index", "5"),
    "precipitation": ("probability_of_precipitation", "0"),
    "wind_direction": ("wind_direction", "SSE"),
    "wind_gust": ("wind_gust", "16"),
    "wind_speed": ("wind_speed", "9"),
    "humidity": ("humidity", "50"),
}


class MockDateTime(datetime):
    """Replacement for datetime that can be mocked for testing."""

    def __new__(cls, *args, **kwargs):
        """Override to just return base class."""
        return datetime.__new__(datetime, *args, **kwargs)


@patch("datetime.datetime", MockDateTime)
async def test_one_weather_site_running(hass, requests_mock):
    """Test the Met Office weather platform."""

    # all metoffice test data encapsulated in here
    mock_json = json.loads(load_fixture("metoffice.json"))
    all_sites = json.dumps(mock_json["all_sites"])
    wavertree_hourly = json.dumps(mock_json["wavertree_hourly"])

    from datetime import datetime, timezone

    MockDateTime.now = classmethod(
        lambda *args, **kwargs: datetime(2020, 4, 25, 12, tzinfo=timezone.utc)
    )

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


@patch("datetime.datetime", MockDateTime)
async def test_one_sensor_site_running(hass, requests_mock):
    """Test the Met Office sensor platform."""

    # all metoffice test data encapsulated in here
    mock_json = json.loads(load_fixture("metoffice.json"))

    all_sites = json.dumps(mock_json["all_sites"])
    wavertree_hourly = json.dumps(mock_json["wavertree_hourly"])

    from datetime import datetime, timezone

    MockDateTime.now = classmethod(
        lambda *args, **kwargs: datetime(2020, 4, 25, 12, tzinfo=timezone.utc)
    )

    requests_mock.get("/public/data/val/wxfcs/all/json/sitelist/", text=all_sites)
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/354107?res=3hourly", text=wavertree_hourly,
    )

    entry = MockConfigEntry(domain=DOMAIN, data=METOFFICE_CONFIG_WAVERTREE,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    for sensor_id in WAVERTREE_SENSOR_RESULTS:
        sensor_name, sensor_value = WAVERTREE_SENSOR_RESULTS[sensor_id]
        _LOGGER.info(f"{sensor_id} / {sensor_name} expecting {sensor_value}")
        sensor = hass.states.get(f"sensor.wavertree_{sensor_name}")
        assert sensor is not None

        assert sensor.state == sensor_value
        assert (
            sensor.attributes.get("last_update").strftime(DATETIME_FORMAT)
            == "2020-04-25 12:00:00+0000"
        )
        assert sensor.attributes.get("sensor_id") == sensor_id
        assert sensor.attributes.get("site_id") == "354107"
        assert sensor.attributes.get("site_name") == TEST_SITE_NAME_WAVERTREE
        assert sensor.attributes.get("attribution") == ATTRIBUTION


@patch("datetime.datetime", MockDateTime)
async def test_site_cannot_connect(hass, requests_mock):
    """Test we handle cannot connect error."""

    from datetime import datetime, timezone

    MockDateTime.now = classmethod(
        lambda *args, **kwargs: datetime(2020, 4, 25, 12, tzinfo=timezone.utc)
    )

    requests_mock.get("/public/data/val/wxfcs/all/json/sitelist/", text="")
    requests_mock.get("/public/data/val/wxfcs/all/json/354107?res=3hourly", text="")
    requests_mock.get("/public/data/val/wxfcs/all/json/322380?res=3hourly", text="")

    entry = MockConfigEntry(domain=DOMAIN, data=METOFFICE_CONFIG_WAVERTREE,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("weather.met_office_kingslynn") is None
    for sensor_id in WAVERTREE_SENSOR_RESULTS:
        sensor_name, sensor_value = WAVERTREE_SENSOR_RESULTS[sensor_id]
        sensor = hass.states.get(f"sensor.kingslynn_{sensor_name}")
        assert sensor is None


@patch("datetime.datetime", MockDateTime)
async def test_two_weather_sites_running(hass, requests_mock):
    """Test we handle two different weather sites both running."""

    from datetime import datetime, timezone

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


@patch("datetime.datetime", MockDateTime)
async def test_two_sensor_sites_running(hass, requests_mock):
    """Test we handle two sets of sensors running for two different sites."""

    from datetime import datetime, timezone

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

    entry = MockConfigEntry(domain=DOMAIN, data=METOFFICE_CONFIG_WAVERTREE,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    entry2 = MockConfigEntry(domain=DOMAIN, data=METOFFICE_CONFIG_KINGSLYNN,)
    entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(entry2.entry_id)
    await hass.async_block_till_done()

    for sensor_id in WAVERTREE_SENSOR_RESULTS:
        sensor_name, sensor_value = WAVERTREE_SENSOR_RESULTS[sensor_id]
        _LOGGER.info(f"{sensor_id} / {sensor_name} expecting {sensor_value}")
        sensor = hass.states.get(f"sensor.wavertree_{sensor_name}")
        assert sensor is not None

        assert sensor.state == sensor_value
        assert (
            sensor.attributes.get("last_update").strftime(DATETIME_FORMAT)
            == "2020-04-25 12:00:00+0000"
        )
        assert sensor.attributes.get("sensor_id") == sensor_id
        assert sensor.attributes.get("site_id") == "354107"
        assert sensor.attributes.get("site_name") == TEST_SITE_NAME_WAVERTREE
        assert sensor.attributes.get("attribution") == ATTRIBUTION

    for sensor_id in KINGSLYNN_SENSOR_RESULTS:
        sensor_name, sensor_value = KINGSLYNN_SENSOR_RESULTS[sensor_id]
        _LOGGER.info(f"{sensor_id} / {sensor_name} expecting {sensor_value}")
        sensor = hass.states.get(f"sensor.king_s_lynn_{sensor_name}")
        assert sensor is not None

        assert sensor.state == sensor_value
        assert (
            sensor.attributes.get("last_update").strftime(DATETIME_FORMAT)
            == "2020-04-25 12:00:00+0000"
        )
        assert sensor.attributes.get("sensor_id") == sensor_id
        assert sensor.attributes.get("site_id") == "322380"
        assert sensor.attributes.get("site_name") == TEST_SITE_NAME_KINGSLYNN
        assert sensor.attributes.get("attribution") == ATTRIBUTION

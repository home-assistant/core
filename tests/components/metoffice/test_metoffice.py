"""The tests for the Met Office weather component."""
from datetime import datetime
import json
import logging

from asynctest import patch

from homeassistant.components.metoffice.const import ATTRIBUTION, DOMAIN

from .const import DATETIME_FORMAT, METOFFICE_CONFIG

from tests.common import MockConfigEntry, load_fixture

_LOGGER = logging.getLogger(__name__)


class MockDateTime(datetime):
    """Replacement for datetime that can be mocked for testing."""

    def __new__(cls, *args, **kwargs):
        """Override to just return base class."""
        return datetime.__new__(datetime, *args, **kwargs)


@patch("datetime.datetime", MockDateTime)
async def test_weather_platform(hass, requests_mock):
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

    entry = MockConfigEntry(domain=DOMAIN, data=METOFFICE_CONFIG,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity = hass.states.get("weather.met_office_wavertree")
    assert entity

    assert entity.state == "sunny"
    assert entity.attributes.get("temperature") == 17
    assert entity.attributes.get("wind_speed") == 9
    assert entity.attributes.get("wind_bearing") == "SSE"
    assert entity.attributes.get("visibility") == "Good - 10-20"
    assert entity.attributes.get("humidity") == 50


@patch("datetime.datetime", MockDateTime)
async def test_sensor_platform(hass, requests_mock):
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

    entry = MockConfigEntry(domain=DOMAIN, data=METOFFICE_CONFIG,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    expected_results = {
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

    for sensor_id in expected_results.keys():
        sensor_name, sensor_value = expected_results[sensor_id]
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
        assert sensor.attributes.get("site_name") == "Wavertree"
        assert sensor.attributes.get("attribution") == ATTRIBUTION

"""The data tests for the Met Office weather component."""
from datetime import datetime, timedelta, timezone
import json

from homeassistant.components.metoffice.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.util import utcnow

from .const import CONFIG_WAVERTREE_3HOURLY, WAVERTREE_SENSOR_RESULTS

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

    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_WAVERTREE_3HOURLY,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("weather.met_office_wavertree") is None
    for sensor_id in WAVERTREE_SENSOR_RESULTS:
        (
            sensor_name,
            sensor_value,  # pylint: disable=unused-variable
        ) = WAVERTREE_SENSOR_RESULTS[sensor_id]
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

    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_WAVERTREE_3HOURLY,)
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

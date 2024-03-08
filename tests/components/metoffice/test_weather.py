"""The tests for the Met Office sensor component."""
import datetime
from datetime import timedelta
import json
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
import requests_mock
from requests_mock.adapter import _Matcher
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.metoffice.const import DEFAULT_SCAN_INTERVAL, DOMAIN
from homeassistant.components.weather import (
    DOMAIN as WEATHER_DOMAIN,
    LEGACY_SERVICE_GET_FORECAST,
    SERVICE_GET_FORECASTS,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import async_get as get_dev_reg
from homeassistant.util import utcnow

from .const import (
    DEVICE_KEY_KINGSLYNN,
    DEVICE_KEY_WAVERTREE,
    METOFFICE_CONFIG_KINGSLYNN,
    METOFFICE_CONFIG_WAVERTREE,
    WAVERTREE_SENSOR_RESULTS,
)

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture
from tests.typing import WebSocketGenerator


@pytest.fixture
def no_sensor():
    """Remove sensors."""
    with patch(
        "homeassistant.components.metoffice.sensor.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def wavertree_data(requests_mock: requests_mock.Mocker) -> dict[str, _Matcher]:
    """Mock data for the Wavertree location."""
    # all metoffice test data encapsulated in here
    mock_json = json.loads(load_fixture("metoffice.json"))
    all_sites = json.dumps(mock_json["all_sites"])
    wavertree_hourly = json.dumps(mock_json["wavertree_hourly"])
    wavertree_daily = json.dumps(mock_json["wavertree_daily"])

    sitelist_mock = requests_mock.get(
        "/public/data/val/wxfcs/all/json/sitelist/", text=all_sites
    )
    wavertree_hourly_mock = requests_mock.get(
        "/public/data/val/wxfcs/all/json/354107?res=3hourly",
        text=wavertree_hourly,
    )
    wavertree_daily_mock = requests_mock.get(
        "/public/data/val/wxfcs/all/json/354107?res=daily",
        text=wavertree_daily,
    )
    return {
        "sitelist_mock": sitelist_mock,
        "wavertree_hourly_mock": wavertree_hourly_mock,
        "wavertree_daily_mock": wavertree_daily_mock,
    }


@pytest.mark.freeze_time(datetime.datetime(2020, 4, 25, 12, tzinfo=datetime.UTC))
async def test_site_cannot_connect(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
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

    dev_reg = get_dev_reg(hass)
    assert len(dev_reg.devices) == 0

    assert hass.states.get("weather.met_office_wavertree_3hourly") is None
    assert hass.states.get("weather.met_office_wavertree_daily") is None
    for sensor_id in WAVERTREE_SENSOR_RESULTS:
        sensor_name, _ = WAVERTREE_SENSOR_RESULTS[sensor_id]
        sensor = hass.states.get(f"sensor.wavertree_{sensor_name}")
        assert sensor is None


@pytest.mark.freeze_time(datetime.datetime(2020, 4, 25, 12, tzinfo=datetime.UTC))
async def test_site_cannot_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    requests_mock: requests_mock.Mocker,
    wavertree_data,
) -> None:
    """Test we handle cannot connect error."""

    # Pre-create the hourly entity
    entity_registry.async_get_or_create(
        WEATHER_DOMAIN,
        DOMAIN,
        "53.38374_-2.90929",
        suggested_object_id="met_office_wavertree_3_hourly",
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    weather = hass.states.get("weather.met_office_wavertree_3_hourly")
    assert weather

    weather = hass.states.get("weather.met_office_wavertree_daily")
    assert weather

    requests_mock.get("/public/data/val/wxfcs/all/json/354107?res=3hourly", text="")
    requests_mock.get("/public/data/val/wxfcs/all/json/354107?res=daily", text="")

    future_time = utcnow() + timedelta(minutes=20)
    async_fire_time_changed(hass, future_time)
    await hass.async_block_till_done()

    weather = hass.states.get("weather.met_office_wavertree_3_hourly")
    assert weather.state == STATE_UNAVAILABLE

    weather = hass.states.get("weather.met_office_wavertree_daily")
    assert weather.state == STATE_UNAVAILABLE


@pytest.mark.freeze_time(datetime.datetime(2020, 4, 25, 12, tzinfo=datetime.UTC))
async def test_one_weather_site_running(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    requests_mock: requests_mock.Mocker,
    wavertree_data,
) -> None:
    """Test the Met Office weather platform."""

    # Pre-create the hourly entity
    entity_registry.async_get_or_create(
        WEATHER_DOMAIN,
        DOMAIN,
        "53.38374_-2.90929",
        suggested_object_id="met_office_wavertree_3_hourly",
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    dev_reg = get_dev_reg(hass)
    assert len(dev_reg.devices) == 1
    device_wavertree = dev_reg.async_get_device(identifiers=DEVICE_KEY_WAVERTREE)
    assert device_wavertree.name == "Met Office Wavertree"

    # Wavertree 3-hourly weather platform expected results
    weather = hass.states.get("weather.met_office_wavertree_3_hourly")
    assert weather

    assert weather.state == "sunny"
    assert weather.attributes.get("temperature") == 17
    assert weather.attributes.get("wind_speed") == 14.48
    assert weather.attributes.get("wind_speed_unit") == "km/h"
    assert weather.attributes.get("wind_bearing") == "SSE"
    assert weather.attributes.get("humidity") == 50

    # Forecasts added - just pick out 1 entry to check
    assert len(weather.attributes.get("forecast")) == 35

    assert (
        weather.attributes.get("forecast")[26]["datetime"]
        == "2020-04-28T21:00:00+00:00"
    )
    assert weather.attributes.get("forecast")[26]["condition"] == "cloudy"
    assert weather.attributes.get("forecast")[26]["precipitation_probability"] == 9
    assert weather.attributes.get("forecast")[26]["temperature"] == 10
    assert weather.attributes.get("forecast")[26]["wind_speed"] == 6.44
    assert weather.attributes.get("forecast")[26]["wind_bearing"] == "NNE"

    # Wavertree daily weather platform expected results
    weather = hass.states.get("weather.met_office_wavertree_daily")
    assert weather

    assert weather.state == "sunny"
    assert weather.attributes.get("temperature") == 19
    assert weather.attributes.get("wind_speed") == 14.48
    assert weather.attributes.get("wind_bearing") == "SSE"
    assert weather.attributes.get("humidity") == 50

    # Also has Forecasts added - again, just pick out 1 entry to check
    # ensures that daily filters out multiple results per day
    assert len(weather.attributes.get("forecast")) == 4

    assert (
        weather.attributes.get("forecast")[3]["datetime"] == "2020-04-29T12:00:00+00:00"
    )
    assert weather.attributes.get("forecast")[3]["condition"] == "rainy"
    assert weather.attributes.get("forecast")[3]["precipitation_probability"] == 59
    assert weather.attributes.get("forecast")[3]["temperature"] == 13
    assert weather.attributes.get("forecast")[3]["wind_speed"] == 20.92
    assert weather.attributes.get("forecast")[3]["wind_bearing"] == "SE"


@pytest.mark.freeze_time(datetime.datetime(2020, 4, 25, 12, tzinfo=datetime.UTC))
async def test_two_weather_sites_running(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    requests_mock: requests_mock.Mocker,
    wavertree_data,
) -> None:
    """Test we handle two different weather sites both running."""

    # Pre-create the hourly entities
    entity_registry.async_get_or_create(
        WEATHER_DOMAIN,
        DOMAIN,
        "53.38374_-2.90929",
        suggested_object_id="met_office_wavertree_3_hourly",
    )
    entity_registry.async_get_or_create(
        WEATHER_DOMAIN,
        DOMAIN,
        "52.75556_0.44231",
        suggested_object_id="met_office_king_s_lynn_3_hourly",
    )

    # all metoffice test data encapsulated in here
    mock_json = json.loads(load_fixture("metoffice.json"))
    kingslynn_hourly = json.dumps(mock_json["kingslynn_hourly"])
    kingslynn_daily = json.dumps(mock_json["kingslynn_daily"])

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

    dev_reg = get_dev_reg(hass)
    assert len(dev_reg.devices) == 2
    device_kingslynn = dev_reg.async_get_device(identifiers=DEVICE_KEY_KINGSLYNN)
    assert device_kingslynn.name == "Met Office King's Lynn"
    device_wavertree = dev_reg.async_get_device(identifiers=DEVICE_KEY_WAVERTREE)
    assert device_wavertree.name == "Met Office Wavertree"

    # Wavertree 3-hourly weather platform expected results
    weather = hass.states.get("weather.met_office_wavertree_3_hourly")
    assert weather

    assert weather.state == "sunny"
    assert weather.attributes.get("temperature") == 17
    assert weather.attributes.get("wind_speed") == 14.48
    assert weather.attributes.get("wind_speed_unit") == "km/h"
    assert weather.attributes.get("wind_bearing") == "SSE"
    assert weather.attributes.get("humidity") == 50

    # Forecasts added - just pick out 1 entry to check
    assert len(weather.attributes.get("forecast")) == 35

    assert (
        weather.attributes.get("forecast")[18]["datetime"]
        == "2020-04-27T21:00:00+00:00"
    )
    assert weather.attributes.get("forecast")[18]["condition"] == "clear-night"
    assert weather.attributes.get("forecast")[18]["precipitation_probability"] == 1
    assert weather.attributes.get("forecast")[18]["temperature"] == 9
    assert weather.attributes.get("forecast")[18]["wind_speed"] == 6.44
    assert weather.attributes.get("forecast")[18]["wind_bearing"] == "NW"

    # Wavertree daily weather platform expected results
    weather = hass.states.get("weather.met_office_wavertree_daily")
    assert weather

    assert weather.state == "sunny"
    assert weather.attributes.get("temperature") == 19
    assert weather.attributes.get("wind_speed") == 14.48
    assert weather.attributes.get("wind_speed_unit") == "km/h"
    assert weather.attributes.get("wind_bearing") == "SSE"
    assert weather.attributes.get("humidity") == 50

    # Also has Forecasts added - again, just pick out 1 entry to check
    # ensures that daily filters out multiple results per day
    assert len(weather.attributes.get("forecast")) == 4

    assert (
        weather.attributes.get("forecast")[3]["datetime"] == "2020-04-29T12:00:00+00:00"
    )
    assert weather.attributes.get("forecast")[3]["condition"] == "rainy"
    assert weather.attributes.get("forecast")[3]["precipitation_probability"] == 59
    assert weather.attributes.get("forecast")[3]["temperature"] == 13
    assert weather.attributes.get("forecast")[3]["wind_speed"] == 20.92
    assert weather.attributes.get("forecast")[3]["wind_bearing"] == "SE"

    # King's Lynn 3-hourly weather platform expected results
    weather = hass.states.get("weather.met_office_king_s_lynn_3_hourly")
    assert weather

    assert weather.state == "sunny"
    assert weather.attributes.get("temperature") == 14
    assert weather.attributes.get("wind_speed") == 3.22
    assert weather.attributes.get("wind_speed_unit") == "km/h"
    assert weather.attributes.get("wind_bearing") == "E"
    assert weather.attributes.get("humidity") == 60

    # Also has Forecast added - just pick out 1 entry to check
    assert len(weather.attributes.get("forecast")) == 35

    assert (
        weather.attributes.get("forecast")[18]["datetime"]
        == "2020-04-27T21:00:00+00:00"
    )
    assert weather.attributes.get("forecast")[18]["condition"] == "cloudy"
    assert weather.attributes.get("forecast")[18]["precipitation_probability"] == 9
    assert weather.attributes.get("forecast")[18]["temperature"] == 10
    assert weather.attributes.get("forecast")[18]["wind_speed"] == 11.27
    assert weather.attributes.get("forecast")[18]["wind_bearing"] == "SE"

    # King's Lynn daily weather platform expected results
    weather = hass.states.get("weather.met_office_king_s_lynn_daily")
    assert weather

    assert weather.state == "cloudy"
    assert weather.attributes.get("temperature") == 9
    assert weather.attributes.get("wind_speed") == 6.44
    assert weather.attributes.get("wind_speed_unit") == "km/h"
    assert weather.attributes.get("wind_bearing") == "ESE"
    assert weather.attributes.get("humidity") == 75

    # All should have Forecast added - again, just picking out 1 entry to check
    # ensures daily filters out multiple results per day
    assert len(weather.attributes.get("forecast")) == 4

    assert (
        weather.attributes.get("forecast")[2]["datetime"] == "2020-04-28T12:00:00+00:00"
    )
    assert weather.attributes.get("forecast")[2]["condition"] == "cloudy"
    assert weather.attributes.get("forecast")[2]["precipitation_probability"] == 14
    assert weather.attributes.get("forecast")[2]["temperature"] == 11
    assert weather.attributes.get("forecast")[2]["wind_speed"] == 11.27
    assert weather.attributes.get("forecast")[2]["wind_bearing"] == "ESE"


@pytest.mark.freeze_time(datetime.datetime(2020, 4, 25, 12, tzinfo=datetime.UTC))
async def test_new_config_entry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, no_sensor, wavertree_data
) -> None:
    """Test the expected entities are created."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(WEATHER_DOMAIN)) == 1
    entry = hass.config_entries.async_entries()[0]
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 1


@pytest.mark.freeze_time(datetime.datetime(2020, 4, 25, 12, tzinfo=datetime.UTC))
async def test_legacy_config_entry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, no_sensor, wavertree_data
) -> None:
    """Test the expected entities are created."""
    # Pre-create the hourly entity
    entity_registry.async_get_or_create(
        WEATHER_DOMAIN,
        DOMAIN,
        "53.38374_-2.90929",
        suggested_object_id="met_office_wavertree_3_hourly",
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids("weather")) == 2
    entry = hass.config_entries.async_entries()[0]
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 2


@pytest.mark.freeze_time(datetime.datetime(2020, 4, 25, 12, tzinfo=datetime.UTC))
@pytest.mark.parametrize(
    ("service"),
    [
        SERVICE_GET_FORECASTS,
        LEGACY_SERVICE_GET_FORECAST,
    ],
)
async def test_forecast_service(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    requests_mock: requests_mock.Mocker,
    snapshot: SnapshotAssertion,
    no_sensor,
    wavertree_data: dict[str, _Matcher],
    service: str,
) -> None:
    """Test multiple forecast."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert wavertree_data["wavertree_daily_mock"].call_count == 1
    assert wavertree_data["wavertree_hourly_mock"].call_count == 1

    for forecast_type in ("daily", "hourly"):
        response = await hass.services.async_call(
            WEATHER_DOMAIN,
            service,
            {
                "entity_id": "weather.met_office_wavertree_daily",
                "type": forecast_type,
            },
            blocking=True,
            return_response=True,
        )
        assert response == snapshot

    # Calling the services should use cached data
    assert wavertree_data["wavertree_daily_mock"].call_count == 1
    assert wavertree_data["wavertree_hourly_mock"].call_count == 1

    # Trigger data refetch
    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert wavertree_data["wavertree_daily_mock"].call_count == 2
    assert wavertree_data["wavertree_hourly_mock"].call_count == 1

    for forecast_type in ("daily", "hourly"):
        response = await hass.services.async_call(
            WEATHER_DOMAIN,
            service,
            {
                "entity_id": "weather.met_office_wavertree_daily",
                "type": forecast_type,
            },
            blocking=True,
            return_response=True,
        )
        assert response == snapshot

    # Calling the services should update the hourly forecast
    assert wavertree_data["wavertree_daily_mock"].call_count == 2
    assert wavertree_data["wavertree_hourly_mock"].call_count == 2

    # Update fails
    requests_mock.get("/public/data/val/wxfcs/all/json/354107?res=3hourly", text="")

    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {
            "entity_id": "weather.met_office_wavertree_daily",
            "type": "hourly",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


@pytest.mark.parametrize(
    "entity_id",
    [
        "weather.met_office_wavertree_3_hourly",
        "weather.met_office_wavertree_daily",
    ],
)
@pytest.mark.freeze_time(datetime.datetime(2020, 4, 25, 12, tzinfo=datetime.UTC))
async def test_forecast_subscription(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    no_sensor,
    wavertree_data: dict[str, _Matcher],
    entity_id: str,
) -> None:
    """Test multiple forecast."""
    client = await hass_ws_client(hass)

    # Pre-create the hourly entity
    entity_registry.async_get_or_create(
        WEATHER_DOMAIN,
        DOMAIN,
        "53.38374_-2.90929",
        suggested_object_id="met_office_wavertree_3_hourly",
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    for forecast_type in ("daily", "hourly"):
        await client.send_json_auto_id(
            {
                "type": "weather/subscribe_forecast",
                "forecast_type": forecast_type,
                "entity_id": entity_id,
            }
        )
        msg = await client.receive_json()
        assert msg["success"]
        assert msg["result"] is None
        subscription_id = msg["id"]

        msg = await client.receive_json()
        assert msg["id"] == subscription_id
        assert msg["type"] == "event"
        forecast1 = msg["event"]["forecast"]

        assert forecast1 != []
        assert forecast1 == snapshot

        freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        msg = await client.receive_json()

        assert msg["id"] == subscription_id
        assert msg["type"] == "event"
        forecast2 = msg["event"]["forecast"]

        assert forecast2 != []
        assert forecast2 == snapshot

        await client.send_json_auto_id(
            {
                "type": "unsubscribe_events",
                "subscription": subscription_id,
            }
        )
        freezer.tick(timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        msg = await client.receive_json()
        assert msg["success"]

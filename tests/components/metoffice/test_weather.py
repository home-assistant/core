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
    SERVICE_GET_FORECASTS,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import utcnow

from .const import (
    DEVICE_KEY_KINGSLYNN,
    DEVICE_KEY_WAVERTREE,
    METOFFICE_CONFIG_KINGSLYNN,
    METOFFICE_CONFIG_WAVERTREE,
    WAVERTREE_SENSOR_RESULTS,
)

from tests.common import MockConfigEntry, async_fire_time_changed, async_load_fixture
from tests.typing import WebSocketGenerator


@pytest.fixture
def no_sensor():
    """Remove sensors."""
    with patch(
        "homeassistant.components.metoffice.sensor.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def wavertree_data(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> dict[str, _Matcher]:
    """Mock data for the Wavertree location."""
    # all metoffice test data encapsulated in here
    mock_json = json.loads(await async_load_fixture(hass, "metoffice.json", DOMAIN))
    wavertree_hourly = json.dumps(mock_json["wavertree_hourly"])
    wavertree_daily = json.dumps(mock_json["wavertree_daily"])

    wavertree_hourly_mock = requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/hourly",
        text=wavertree_hourly,
    )
    wavertree_daily_mock = requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/daily",
        text=wavertree_daily,
    )
    return {
        "wavertree_hourly_mock": wavertree_hourly_mock,
        "wavertree_daily_mock": wavertree_daily_mock,
    }


@pytest.mark.freeze_time(datetime.datetime(2024, 11, 23, 12, tzinfo=datetime.UTC))
async def test_site_cannot_connect(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    requests_mock: requests_mock.Mocker,
) -> None:
    """Test we handle cannot connect error."""

    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/hourly",
        text="",
    )
    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/daily",
        text="",
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(device_registry.devices) == 0

    assert hass.states.get("weather.met_office_wavertree") is None
    for sensor in WAVERTREE_SENSOR_RESULTS.values():
        sensor_name = sensor[0]
        sensor = hass.states.get(f"sensor.wavertree_{sensor_name}")
        assert sensor is None


@pytest.mark.freeze_time(datetime.datetime(2024, 11, 23, 12, tzinfo=datetime.UTC))
async def test_site_cannot_update(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
    wavertree_data,
) -> None:
    """Test we handle cannot connect error."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    weather = hass.states.get("weather.met_office_wavertree")
    assert weather

    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/hourly",
        text="",
    )
    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/daily",
        text="",
    )

    future_time = utcnow() + timedelta(minutes=40)
    async_fire_time_changed(hass, future_time)
    await hass.async_block_till_done(wait_background_tasks=True)

    weather = hass.states.get("weather.met_office_wavertree")
    assert weather.state == STATE_UNAVAILABLE

    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/hourly",
        status_code=404,
    )
    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/daily",
        status_code=404,
    )

    future_time = utcnow() + timedelta(minutes=40)
    async_fire_time_changed(hass, future_time)
    await hass.async_block_till_done(wait_background_tasks=True)

    weather = hass.states.get("weather.met_office_wavertree")
    assert weather.state == STATE_UNAVAILABLE


@pytest.mark.freeze_time(datetime.datetime(2024, 11, 23, 12, tzinfo=datetime.UTC))
async def test_one_weather_site_running(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    requests_mock: requests_mock.Mocker,
    wavertree_data,
) -> None:
    """Test the Met Office weather platform."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(device_registry.devices) == 1
    device_wavertree = device_registry.async_get_device(
        identifiers=DEVICE_KEY_WAVERTREE
    )
    assert device_wavertree.name == "Met Office Wavertree"

    # Wavertree daily weather platform expected results
    weather = hass.states.get("weather.met_office_wavertree")
    assert weather

    assert weather.state == "rainy"
    assert weather.attributes.get("temperature") == 9.3
    assert weather.attributes.get("wind_speed") == 28.33
    assert weather.attributes.get("wind_bearing") == 176.0
    assert weather.attributes.get("humidity") == 95


@pytest.mark.freeze_time(datetime.datetime(2024, 11, 23, 12, tzinfo=datetime.UTC))
async def test_two_weather_sites_running(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    requests_mock: requests_mock.Mocker,
    wavertree_data,
) -> None:
    """Test we handle two different weather sites both running."""

    # all metoffice test data encapsulated in here
    mock_json = json.loads(await async_load_fixture(hass, "metoffice.json", DOMAIN))
    kingslynn_hourly = json.dumps(mock_json["kingslynn_hourly"])
    kingslynn_daily = json.dumps(mock_json["kingslynn_daily"])

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/hourly",
        text=kingslynn_hourly,
    )
    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/daily",
        text=kingslynn_daily,
    )

    entry2 = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_KINGSLYNN,
    )
    entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(entry2.entry_id)
    await hass.async_block_till_done()

    assert len(device_registry.devices) == 2
    device_kingslynn = device_registry.async_get_device(
        identifiers=DEVICE_KEY_KINGSLYNN
    )
    assert device_kingslynn.name == "Met Office King's Lynn"
    device_wavertree = device_registry.async_get_device(
        identifiers=DEVICE_KEY_WAVERTREE
    )
    assert device_wavertree.name == "Met Office Wavertree"

    # Wavertree daily weather platform expected results
    weather = hass.states.get("weather.met_office_wavertree")
    assert weather

    assert weather.state == "rainy"
    assert weather.attributes.get("temperature") == 9.3
    assert weather.attributes.get("wind_speed") == 28.33
    assert weather.attributes.get("wind_speed_unit") == "km/h"
    assert weather.attributes.get("wind_bearing") == 176.0
    assert weather.attributes.get("humidity") == 95

    # King's Lynn daily weather platform expected results
    weather = hass.states.get("weather.met_office_king_s_lynn")
    assert weather

    assert weather.state == "rainy"
    assert weather.attributes.get("temperature") == 7.9
    assert weather.attributes.get("wind_speed") == 35.75
    assert weather.attributes.get("wind_speed_unit") == "km/h"
    assert weather.attributes.get("wind_bearing") == 180.0
    assert weather.attributes.get("humidity") == 98


@pytest.mark.freeze_time(datetime.datetime(2024, 11, 23, 12, tzinfo=datetime.UTC))
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


@pytest.mark.freeze_time(datetime.datetime(2024, 11, 23, 12, tzinfo=datetime.UTC))
@pytest.mark.parametrize(
    ("service"),
    [SERVICE_GET_FORECASTS],
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

    for forecast_type in ("daily", "hourly", "twice_daily"):
        response = await hass.services.async_call(
            WEATHER_DOMAIN,
            service,
            {
                "entity_id": "weather.met_office_wavertree",
                "type": forecast_type,
            },
            blocking=True,
            return_response=True,
        )
        assert response == snapshot

    # Trigger data refetch
    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    for forecast_type in ("daily", "hourly", "twice_daily"):
        response = await hass.services.async_call(
            WEATHER_DOMAIN,
            service,
            {
                "entity_id": "weather.met_office_wavertree",
                "type": forecast_type,
            },
            blocking=True,
            return_response=True,
        )
        assert response == snapshot


@pytest.mark.freeze_time(datetime.datetime(2024, 11, 23, 12, tzinfo=datetime.UTC))
async def test_legacy_config_entry_is_removed(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, no_sensor, wavertree_data
) -> None:
    """Test the expected entities are created."""
    # Pre-create the daily entity
    entity_registry.async_get_or_create(
        WEATHER_DOMAIN,
        DOMAIN,
        "53.38374_-2.90929",
        suggested_object_id="met_office_wavertree_daily",
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids("weather")) == 1
    entry = hass.config_entries.async_entries()[0]
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 1


@pytest.mark.freeze_time(datetime.datetime(2024, 11, 23, 12, tzinfo=datetime.UTC))
async def test_forecast_subscription(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    no_sensor,
    wavertree_data: dict[str, _Matcher],
) -> None:
    """Test multiple forecast."""
    client = await hass_ws_client(hass)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await client.send_json_auto_id(
        {
            "type": "weather/subscribe_forecast",
            "forecast_type": "hourly",
            "entity_id": "weather.met_office_wavertree",
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
    await hass.async_block_till_done(wait_background_tasks=True)
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
    await hass.async_block_till_done(wait_background_tasks=True)
    msg = await client.receive_json()
    assert msg["success"]

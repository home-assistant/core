"""Test for the smhi weather entity."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
from pysmhi import SMHIForecast, SmhiForecastException, SMHIPointForecast
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.smhi.const import DOMAIN
from homeassistant.components.smhi.weather import (
    ATTR_SMHI_THUNDER_PROBABILITY,
    CONDITION_CLASSES,
)
from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_FORECAST_CONDITION,
    ATTR_WEATHER_WIND_GUST_SPEED,
    ATTR_WEATHER_WIND_SPEED_UNIT,
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import ENTITY_ID, TEST_CONFIG

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import WebSocketGenerator


@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.WEATHER]],
)
async def test_setup_hass(
    hass: HomeAssistant,
    load_int: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for successfully setting up the smhi integration."""

    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.state == "fog"
    assert state.attributes == snapshot


@pytest.mark.parametrize(
    "to_load",
    [1],
)
@freeze_time(datetime(2023, 8, 7, 1, tzinfo=dt_util.UTC))
async def test_clear_night(
    hass: HomeAssistant,
    mock_client: SMHIPointForecast,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for successfully setting up the smhi integration."""
    hass.config.latitude = "59.32624"
    hass.config.longitude = "17.84197"
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG,
        entry_id="01JMZDH8N5PFHGJNYKKYCSCWER",
        unique_id="59.32624-17.84197",
        version=3,
        title="Test",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.state == ATTR_CONDITION_CLEAR_NIGHT
    assert state.attributes == snapshot(name="clear_night")

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": ENTITY_ID, "type": "hourly"},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot(name="clear-night_forecast")


async def test_properties_no_data(
    hass: HomeAssistant,
    load_int: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test properties when no API data available."""

    mock_client.async_get_daily_forecast.side_effect = SmhiForecastException("boom")
    freezer.tick(timedelta(minutes=35))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.name == "Test"
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes[ATTR_ATTRIBUTION] == "Swedish weather institute (SMHI)"

    mock_client.async_get_daily_forecast.side_effect = None
    mock_client.async_get_daily_forecast.return_value = None
    freezer.tick(timedelta(minutes=35))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.name == "Test"
    assert state.state == "fog"
    assert ATTR_SMHI_THUNDER_PROBABILITY not in state.attributes
    assert state.attributes[ATTR_ATTRIBUTION] == "Swedish weather institute (SMHI)"


async def test_properties_unknown_symbol(
    hass: HomeAssistant,
    mock_client: MagicMock,
) -> None:
    """Test behaviour when unknown symbol from API."""
    data = SMHIForecast(
        frozen_precipitation=0,
        high_cloud=100,
        humidity=96,
        low_cloud=100,
        max_precipitation=0.0,
        mean_precipitation=0.0,
        median_precipitation=0.0,
        medium_cloud=75,
        min_precipitation=0.0,
        precipitation_category=0,
        pressure=1018.9,
        symbol=100,  # Faulty symbol
        temperature=1.0,
        temperature_max=1.0,
        temperature_min=1.0,
        thunder=0,
        total_cloud=100,
        valid_time=datetime(2018, 1, 1, 0, 0, 0),
        visibility=8.8,
        wind_direction=114,
        wind_gust=5.8,
        wind_speed=2.5,
    )
    data2 = SMHIForecast(
        frozen_precipitation=0,
        high_cloud=100,
        humidity=96,
        low_cloud=100,
        max_precipitation=0.0,
        mean_precipitation=0.0,
        median_precipitation=0.0,
        medium_cloud=75,
        min_precipitation=0.0,
        precipitation_category=0,
        pressure=1018.9,
        symbol=100,  # Faulty symbol
        temperature=1.0,
        temperature_max=1.0,
        temperature_min=1.0,
        thunder=0,
        total_cloud=100,
        valid_time=datetime(2018, 1, 1, 12, 0, 0),
        visibility=8.8,
        wind_direction=114,
        wind_gust=5.8,
        wind_speed=2.5,
    )
    data3 = SMHIForecast(
        frozen_precipitation=0,
        high_cloud=100,
        humidity=96,
        low_cloud=100,
        max_precipitation=0.0,
        mean_precipitation=0.0,
        median_precipitation=0.0,
        medium_cloud=75,
        min_precipitation=0.0,
        precipitation_category=0,
        pressure=1018.9,
        symbol=100,  # Faulty symbol
        temperature=1.0,
        temperature_max=1.0,
        temperature_min=1.0,
        thunder=0,
        total_cloud=100,
        valid_time=datetime(2018, 1, 2, 0, 0, 0),
        visibility=8.8,
        wind_direction=114,
        wind_gust=5.8,
        wind_speed=2.5,
    )

    testdata = [data, data2, data3]

    mock_client.async_get_daily_forecast.return_value = testdata

    entry = MockConfigEntry(domain="smhi", title="test", data=TEST_CONFIG, version=3)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.name == "test"
    assert state.state == STATE_UNKNOWN
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": ENTITY_ID, "type": "daily"},
        blocking=True,
        return_response=True,
    )
    assert all(
        forecast[ATTR_FORECAST_CONDITION] is None
        for forecast in response[ENTITY_ID]["forecast"]
    )


@pytest.mark.parametrize("error", [SmhiForecastException(), TimeoutError()])
async def test_refresh_weather_forecast_retry(
    hass: HomeAssistant,
    error: Exception,
    load_int: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the refresh weather forecast function."""

    mock_client.async_get_daily_forecast.side_effect = error

    freezer.tick(timedelta(minutes=35))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.name == "Test"
    assert state.state == STATE_UNAVAILABLE
    assert mock_client.async_get_daily_forecast.call_count == 2

    freezer.tick(timedelta(minutes=35))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNAVAILABLE
    assert mock_client.async_get_daily_forecast.call_count == 3


def test_condition_class() -> None:
    """Test condition class."""

    def get_condition(index: int) -> str:
        """Return condition given index."""
        return [k for k, v in CONDITION_CLASSES.items() if index in v][0]

    # SMHI definitions as follows, see
    # http://opendata.smhi.se/apidocs/metfcst/parameters.html

    # 1. Clear sky
    assert get_condition(1) == "sunny"
    # 2. Nearly clear sky
    assert get_condition(2) == "sunny"
    # 3. Variable cloudiness
    assert get_condition(3) == "partlycloudy"
    # 4. Halfclear sky
    assert get_condition(4) == "partlycloudy"
    # 5. Cloudy sky
    assert get_condition(5) == "cloudy"
    # 6. Overcast
    assert get_condition(6) == "cloudy"
    # 7. Fog
    assert get_condition(7) == "fog"
    # 8. Light rain showers
    assert get_condition(8) == "rainy"
    # 9. Moderate rain showers
    assert get_condition(9) == "rainy"
    # 18. Light rain
    assert get_condition(18) == "rainy"
    # 19. Moderate rain
    assert get_condition(19) == "rainy"
    # 10. Heavy rain showers
    assert get_condition(10) == "pouring"
    # 20. Heavy rain
    assert get_condition(20) == "pouring"
    # 21. Thunder
    assert get_condition(21) == "lightning"
    # 11. Thunderstorm
    assert get_condition(11) == "lightning-rainy"
    # 15. Light snow showers
    assert get_condition(15) == "snowy"
    # 16. Moderate snow showers
    assert get_condition(16) == "snowy"
    # 17. Heavy snow showers
    assert get_condition(17) == "snowy"
    # 25. Light snowfall
    assert get_condition(25) == "snowy"
    # 26. Moderate snowfall
    assert get_condition(26) == "snowy"
    # 27. Heavy snowfall
    assert get_condition(27) == "snowy"
    # 12. Light sleet showers
    assert get_condition(12) == "snowy-rainy"
    # 13. Moderate sleet showers
    assert get_condition(13) == "snowy-rainy"
    # 14. Heavy sleet showers
    assert get_condition(14) == "snowy-rainy"
    # 22. Light sleet
    assert get_condition(22) == "snowy-rainy"
    # 23. Moderate sleet
    assert get_condition(23) == "snowy-rainy"
    # 24. Heavy sleet
    assert get_condition(24) == "snowy-rainy"


async def test_custom_speed_unit(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    load_int: MockConfigEntry,
) -> None:
    """Test Wind Gust speed with custom unit."""
    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.name == "Test"
    assert state.attributes[ATTR_WEATHER_WIND_GUST_SPEED] == 22.32

    entity_registry.async_update_entity_options(
        state.entity_id,
        WEATHER_DOMAIN,
        {ATTR_WEATHER_WIND_SPEED_UNIT: UnitOfSpeed.METERS_PER_SECOND},
    )

    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_WEATHER_WIND_GUST_SPEED] == 6.2


@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.WEATHER]],
)
async def test_forecast_services(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    load_int: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test multiple forecast."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "weather/subscribe_forecast",
            "forecast_type": "daily",
            "entity_id": ENTITY_ID,
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

    assert len(forecast1) == 10
    assert forecast1[0] == snapshot
    assert forecast1[6] == snapshot

    await client.send_json_auto_id(
        {
            "type": "weather/subscribe_forecast",
            "forecast_type": "hourly",
            "entity_id": ENTITY_ID,
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

    assert len(forecast1) == 52
    assert forecast1[0] == snapshot
    assert forecast1[6] == snapshot


@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.WEATHER]],
)
@pytest.mark.parametrize(
    "to_load",
    [2],
)
async def test_forecast_services_lack_of_data(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    load_int: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test forecast lacking data."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "weather/subscribe_forecast",
            "forecast_type": "daily",
            "entity_id": ENTITY_ID,
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

    assert forecast1 is None


@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.WEATHER]],
)
async def test_forecast_service(
    hass: HomeAssistant,
    load_int: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test forecast service."""
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": ENTITY_ID, "type": "daily"},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.WEATHER]],
)
async def test_twice_daily_forecast_service(
    hass: HomeAssistant,
    load_int: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test forecast service."""
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": ENTITY_ID, "type": "twice_daily"},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot

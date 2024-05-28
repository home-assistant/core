"""Tests for Tomorrow.io weather entity."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.tomorrowio.config_flow import (
    _get_config_schema,
    _get_unique_id,
)
from homeassistant.components.tomorrowio.const import (
    ATTRIBUTION,
    CONF_TIMESTEP,
    DEFAULT_NAME,
    DEFAULT_TIMESTEP,
    DOMAIN,
)
from homeassistant.components.weather import (
    ATTR_CONDITION_SUNNY,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_OZONE,
    ATTR_WEATHER_PRECIPITATION_UNIT,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_PRESSURE_UNIT,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_TEMPERATURE_UNIT,
    ATTR_WEATHER_VISIBILITY,
    ATTR_WEATHER_VISIBILITY_UNIT,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED,
    ATTR_WEATHER_WIND_SPEED_UNIT,
    DOMAIN as WEATHER_DOMAIN,
    LEGACY_SERVICE_GET_FORECAST,
    SERVICE_GET_FORECASTS,
)
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY, SOURCE_USER
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_FRIENDLY_NAME, CONF_NAME
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import async_get
from homeassistant.util import dt as dt_util

from .const import API_V4_ENTRY_DATA

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import WebSocketGenerator


@callback
def _enable_entity(hass: HomeAssistant, entity_name: str) -> None:
    """Enable disabled entity."""
    ent_reg = async_get(hass)
    entry = ent_reg.async_get(entity_name)
    updated_entry = ent_reg.async_update_entity(entry.entity_id, disabled_by=None)
    assert updated_entry != entry
    assert updated_entry.disabled is False


async def _setup_config_entry(hass: HomeAssistant, config: dict[str, Any]) -> State:
    """Set up entry and return entity state."""
    data = _get_config_schema(hass, SOURCE_USER)(config)
    data[CONF_NAME] = DEFAULT_NAME
    config_entry = MockConfigEntry(
        title=DEFAULT_NAME,
        domain=DOMAIN,
        data=data,
        options={CONF_TIMESTEP: DEFAULT_TIMESTEP},
        unique_id=_get_unique_id(hass, data),
        version=1,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def _setup(hass: HomeAssistant, config: dict[str, Any]) -> State:
    """Set up entry and return entity state."""
    with freeze_time(datetime(2021, 3, 6, 23, 59, 59, tzinfo=dt_util.UTC)):
        await _setup_config_entry(hass, config)

    return hass.states.get("weather.tomorrow_io_daily")


async def _setup_legacy(hass: HomeAssistant, config: dict[str, Any]) -> State:
    """Set up entry and return entity state."""
    registry = er.async_get(hass)
    data = _get_config_schema(hass, SOURCE_USER)(config)
    for entity_name in ("hourly", "nowcast"):
        registry.async_get_or_create(
            WEATHER_DOMAIN,
            DOMAIN,
            f"{_get_unique_id(hass, data)}_{entity_name}",
            disabled_by=er.RegistryEntryDisabler.INTEGRATION,
            suggested_object_id=f"tomorrow_io_{entity_name}",
        )

    with freeze_time(
        datetime(2021, 3, 6, 23, 59, 59, tzinfo=dt_util.UTC)
    ) as frozen_time:
        await _setup_config_entry(hass, config)
        for entity_name in ("hourly", "nowcast"):
            _enable_entity(hass, f"weather.tomorrow_io_{entity_name}")
        await hass.async_block_till_done()
        # the enabled entity state will be fired in RELOAD_AFTER_UPDATE_DELAY
        frozen_time.tick(delta=RELOAD_AFTER_UPDATE_DELAY)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert len(hass.states.async_entity_ids(WEATHER_DOMAIN)) == 3

    return hass.states.get("weather.tomorrow_io_daily")


async def test_new_config_entry(hass: HomeAssistant) -> None:
    """Test the expected entities are created."""
    registry = er.async_get(hass)
    await _setup(hass, API_V4_ENTRY_DATA)
    assert len(hass.states.async_entity_ids("weather")) == 1

    entry = hass.config_entries.async_entries()[0]
    assert len(er.async_entries_for_config_entry(registry, entry.entry_id)) == 28


async def test_legacy_config_entry(hass: HomeAssistant) -> None:
    """Test the expected entities are created."""
    registry = er.async_get(hass)
    data = _get_config_schema(hass, SOURCE_USER)(API_V4_ENTRY_DATA)
    for entity_name in ("hourly", "nowcast"):
        registry.async_get_or_create(
            WEATHER_DOMAIN,
            DOMAIN,
            f"{_get_unique_id(hass, data)}_{entity_name}",
        )
    await _setup(hass, API_V4_ENTRY_DATA)
    assert len(hass.states.async_entity_ids("weather")) == 3

    entry = hass.config_entries.async_entries()[0]
    assert len(er.async_entries_for_config_entry(registry, entry.entry_id)) == 30


async def test_v4_weather(hass: HomeAssistant, tomorrowio_config_entry_update) -> None:
    """Test v4 weather data."""
    weather_state = await _setup(hass, API_V4_ENTRY_DATA)

    tomorrowio_config_entry_update.assert_called_with(
        [
            "temperature",
            "humidity",
            "pressureSeaLevel",
            "windSpeed",
            "windDirection",
            "weatherCode",
            "visibility",
            "pollutantO3",
            "windGust",
            "cloudCover",
            "precipitationType",
            "pollutantCO",
            "mepIndex",
            "mepHealthConcern",
            "mepPrimaryPollutant",
            "cloudBase",
            "cloudCeiling",
            "cloudCover",
            "dewPoint",
            "epaIndex",
            "epaHealthConcern",
            "epaPrimaryPollutant",
            "temperatureApparent",
            "fireIndex",
            "pollutantNO2",
            "pollutantO3",
            "particulateMatter10",
            "particulateMatter25",
            "grassIndex",
            "treeIndex",
            "weedIndex",
            "precipitationType",
            "pressureSurfaceLevel",
            "solarGHI",
            "pollutantSO2",
            "uvIndex",
            "uvHealthConcern",
            "windGust",
        ],
        [
            "temperatureMin",
            "temperatureMax",
            "dewPoint",
            "humidity",
            "windSpeed",
            "windDirection",
            "weatherCode",
            "precipitationIntensityAvg",
            "precipitationProbability",
        ],
        nowcast_timestep=60,
        location="80.0,80.0",
    )

    assert weather_state.state == ATTR_CONDITION_SUNNY
    assert weather_state.attributes[ATTR_ATTRIBUTION] == ATTRIBUTION
    assert weather_state.attributes[ATTR_FRIENDLY_NAME] == "Tomorrow.io Daily"
    assert weather_state.attributes[ATTR_WEATHER_HUMIDITY] == 23
    assert weather_state.attributes[ATTR_WEATHER_OZONE] == 46.53
    assert weather_state.attributes[ATTR_WEATHER_PRECIPITATION_UNIT] == "mm"
    assert weather_state.attributes[ATTR_WEATHER_PRESSURE] == 30.35
    assert weather_state.attributes[ATTR_WEATHER_PRESSURE_UNIT] == "hPa"
    assert weather_state.attributes[ATTR_WEATHER_TEMPERATURE] == 44.1
    assert weather_state.attributes[ATTR_WEATHER_TEMPERATURE_UNIT] == "°C"
    assert weather_state.attributes[ATTR_WEATHER_VISIBILITY] == 8.15
    assert weather_state.attributes[ATTR_WEATHER_VISIBILITY_UNIT] == "km"
    assert weather_state.attributes[ATTR_WEATHER_WIND_BEARING] == 315.14
    assert weather_state.attributes[ATTR_WEATHER_WIND_SPEED] == 33.59  # 9.33 m/s ->km/h
    assert weather_state.attributes[ATTR_WEATHER_WIND_SPEED_UNIT] == "km/h"


async def test_v4_weather_legacy_entities(hass: HomeAssistant) -> None:
    """Test v4 weather data."""
    weather_state = await _setup_legacy(hass, API_V4_ENTRY_DATA)
    assert weather_state.state == ATTR_CONDITION_SUNNY
    assert weather_state.attributes[ATTR_ATTRIBUTION] == ATTRIBUTION
    assert weather_state.attributes[ATTR_FRIENDLY_NAME] == "Tomorrow.io Daily"
    assert weather_state.attributes[ATTR_WEATHER_HUMIDITY] == 23
    assert weather_state.attributes[ATTR_WEATHER_OZONE] == 46.53
    assert weather_state.attributes[ATTR_WEATHER_PRECIPITATION_UNIT] == "mm"
    assert weather_state.attributes[ATTR_WEATHER_PRESSURE] == 30.35
    assert weather_state.attributes[ATTR_WEATHER_PRESSURE_UNIT] == "hPa"
    assert weather_state.attributes[ATTR_WEATHER_TEMPERATURE] == 44.1
    assert weather_state.attributes[ATTR_WEATHER_TEMPERATURE_UNIT] == "°C"
    assert weather_state.attributes[ATTR_WEATHER_VISIBILITY] == 8.15
    assert weather_state.attributes[ATTR_WEATHER_VISIBILITY_UNIT] == "km"
    assert weather_state.attributes[ATTR_WEATHER_WIND_BEARING] == 315.14
    assert weather_state.attributes[ATTR_WEATHER_WIND_SPEED] == 33.59  # 9.33 m/s ->km/h
    assert weather_state.attributes[ATTR_WEATHER_WIND_SPEED_UNIT] == "km/h"


@pytest.mark.parametrize(
    ("service"),
    [
        SERVICE_GET_FORECASTS,
        LEGACY_SERVICE_GET_FORECAST,
    ],
)
@freeze_time(datetime(2021, 3, 6, 23, 59, 59, tzinfo=dt_util.UTC))
async def test_v4_forecast_service(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    service: str,
) -> None:
    """Test multiple forecast."""
    weather_state = await _setup(hass, API_V4_ENTRY_DATA)
    entity_id = weather_state.entity_id

    for forecast_type in ("daily", "hourly"):
        response = await hass.services.async_call(
            WEATHER_DOMAIN,
            service,
            {
                "entity_id": entity_id,
                "type": forecast_type,
            },
            blocking=True,
            return_response=True,
        )
        assert response == snapshot


async def test_legacy_v4_bad_forecast(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tomorrowio_config_entry_update,
    snapshot: SnapshotAssertion,
) -> None:
    """Test bad forecast data."""
    freezer.move_to(datetime(2021, 3, 6, 23, 59, 59, tzinfo=dt_util.UTC))

    weather_state = await _setup(hass, API_V4_ENTRY_DATA)
    entity_id = weather_state.entity_id
    hourly_forecast = tomorrowio_config_entry_update.return_value["forecasts"]["hourly"]
    hourly_forecast[0]["values"]["precipitationProbability"] = "blah"

    # Trigger data refetch
    freezer.tick(timedelta(minutes=32) + timedelta(seconds=1))
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        LEGACY_SERVICE_GET_FORECAST,
        {
            "entity_id": entity_id,
            "type": "hourly",
        },
        blocking=True,
        return_response=True,
    )
    assert response["forecast"][0]["precipitation_probability"] is None


async def test_v4_bad_forecast(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    tomorrowio_config_entry_update,
    snapshot: SnapshotAssertion,
) -> None:
    """Test bad forecast data."""
    freezer.move_to(datetime(2021, 3, 6, 23, 59, 59, tzinfo=dt_util.UTC))

    weather_state = await _setup(hass, API_V4_ENTRY_DATA)
    entity_id = weather_state.entity_id
    hourly_forecast = tomorrowio_config_entry_update.return_value["forecasts"]["hourly"]
    hourly_forecast[0]["values"]["precipitationProbability"] = "blah"

    # Trigger data refetch
    freezer.tick(timedelta(minutes=32) + timedelta(seconds=1))
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {
            "entity_id": entity_id,
            "type": "hourly",
        },
        blocking=True,
        return_response=True,
    )
    assert (
        response["weather.tomorrow_io_daily"]["forecast"][0][
            "precipitation_probability"
        ]
        is None
    )


@pytest.mark.parametrize("forecast_type", ["daily", "hourly"])
async def test_forecast_subscription(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    forecast_type: str,
) -> None:
    """Test multiple forecast."""
    client = await hass_ws_client(hass)
    freezer.move_to(datetime(2021, 3, 6, 23, 59, 59, tzinfo=dt_util.UTC))

    weather_state = await _setup(hass, API_V4_ENTRY_DATA)
    entity_id = weather_state.entity_id

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

    freezer.tick(timedelta(minutes=32) + timedelta(seconds=1))
    await hass.async_block_till_done()
    msg = await client.receive_json()

    assert msg["id"] == subscription_id
    assert msg["type"] == "event"
    forecast2 = msg["event"]["forecast"]

    assert forecast2 != []
    assert forecast2 == snapshot

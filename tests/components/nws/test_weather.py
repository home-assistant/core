"""Tests for the NWS weather component."""

from datetime import timedelta

import aiohttp
from freezegun.api import FrozenDateTimeFactory
from pynws import NwsNoDataError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import nws
from homeassistant.components.nws.const import (
    DEFAULT_SCAN_INTERVAL,
    OBSERVATION_VALID_TIME,
)
from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_SUNNY,
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

from .const import (
    CLEAR_NIGHT_OBSERVATION,
    EXPECTED_FORECAST_IMPERIAL,
    EXPECTED_FORECAST_METRIC,
    NONE_FORECAST,
    NONE_OBSERVATION,
    NWS_CONFIG,
    WEATHER_EXPECTED_OBSERVATION_IMPERIAL,
    WEATHER_EXPECTED_OBSERVATION_METRIC,
)

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import WebSocketGenerator


@pytest.mark.parametrize(
    ("units", "result_observation", "result_forecast"),
    [
        (
            US_CUSTOMARY_SYSTEM,
            WEATHER_EXPECTED_OBSERVATION_IMPERIAL,
            EXPECTED_FORECAST_IMPERIAL,
        ),
        (METRIC_SYSTEM, WEATHER_EXPECTED_OBSERVATION_METRIC, EXPECTED_FORECAST_METRIC),
    ],
)
async def test_imperial_metric(
    hass: HomeAssistant,
    units,
    result_observation,
    result_forecast,
    mock_simple_nws,
    no_sensor,
) -> None:
    """Test with imperial and metric units."""
    hass.config.units = units
    entry = MockConfigEntry(
        domain=nws.DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.abc")

    assert state
    assert state.state == ATTR_CONDITION_SUNNY

    data = state.attributes
    for key, value in result_observation.items():
        assert data.get(key) == value


async def test_night_clear(hass: HomeAssistant, mock_simple_nws, no_sensor) -> None:
    """Test with clear-night in observation."""
    instance = mock_simple_nws.return_value
    instance.observation = CLEAR_NIGHT_OBSERVATION

    entry = MockConfigEntry(
        domain=nws.DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.abc")
    assert state.state == ATTR_CONDITION_CLEAR_NIGHT


async def test_none_values(hass: HomeAssistant, mock_simple_nws, no_sensor) -> None:
    """Test with none values in observation and forecast dicts."""
    instance = mock_simple_nws.return_value
    instance.observation = NONE_OBSERVATION
    instance.forecast = NONE_FORECAST

    entry = MockConfigEntry(
        domain=nws.DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.abc")
    assert state.state == STATE_UNKNOWN
    data = state.attributes
    for key in WEATHER_EXPECTED_OBSERVATION_IMPERIAL:
        assert data.get(key) is None


async def test_data_caching_error_observation(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_simple_nws,
    no_sensor,
    caplog,
) -> None:
    """Test caching of data with errors."""
    instance = mock_simple_nws.return_value

    entry = MockConfigEntry(
        domain=nws.DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.abc")
    assert state.state == "sunny"

    # data is still valid even when update fails
    instance.update_observation.side_effect = NwsNoDataError("Test")

    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=100))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("weather.abc")
    assert state.state == "sunny"

    assert (
        "NWS observation update failed, but data still valid. Last success: "
        in caplog.text
    )

    # data is no longer valid after OBSERVATION_VALID_TIME
    freezer.tick(OBSERVATION_VALID_TIME + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("weather.abc")
    assert state.state == STATE_UNAVAILABLE

    assert "Error fetching NWS observation station ABC data: Test" in caplog.text


async def test_no_data_error_observation(
    hass: HomeAssistant, mock_simple_nws, no_sensor, caplog
) -> None:
    """Test catching NwsNoDataDrror."""
    instance = mock_simple_nws.return_value
    instance.update_observation.side_effect = NwsNoDataError("Test")

    entry = MockConfigEntry(
        domain=nws.DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert "Error fetching NWS observation station ABC data: Test" in caplog.text


async def test_no_data_error_forecast(
    hass: HomeAssistant, mock_simple_nws, no_sensor, caplog
) -> None:
    """Test catching NwsNoDataDrror."""
    instance = mock_simple_nws.return_value
    instance.update_forecast.side_effect = NwsNoDataError("Test")

    entry = MockConfigEntry(
        domain=nws.DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (
        "Error fetching NWS forecast station ABC data: No data returned" in caplog.text
    )


async def test_no_data_error_forecast_hourly(
    hass: HomeAssistant, mock_simple_nws, no_sensor, caplog
) -> None:
    """Test catching NwsNoDataDrror."""
    instance = mock_simple_nws.return_value
    instance.update_forecast_hourly.side_effect = NwsNoDataError("Test")

    entry = MockConfigEntry(
        domain=nws.DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (
        "Error fetching NWS forecast hourly station ABC data: No data returned"
        in caplog.text
    )


async def test_none(hass: HomeAssistant, mock_simple_nws, no_sensor) -> None:
    """Test with None as observation and forecast."""
    instance = mock_simple_nws.return_value
    instance.observation = None
    instance.forecast = None

    entry = MockConfigEntry(
        domain=nws.DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.abc")
    assert state
    assert state.state == STATE_UNKNOWN

    data = state.attributes
    for key in WEATHER_EXPECTED_OBSERVATION_IMPERIAL:
        assert data.get(key) is None


async def test_error_station(hass: HomeAssistant, mock_simple_nws, no_sensor) -> None:
    """Test error in setting station."""

    instance = mock_simple_nws.return_value
    instance.set_station.side_effect = aiohttp.ClientError

    entry = MockConfigEntry(
        domain=nws.DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("weather.abc") is None


async def test_entity_refresh(hass: HomeAssistant, mock_simple_nws, no_sensor) -> None:
    """Test manual refresh."""
    instance = mock_simple_nws.return_value

    await async_setup_component(hass, "homeassistant", {})

    entry = MockConfigEntry(
        domain=nws.DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    instance.update_observation.assert_called_once()
    instance.update_forecast.assert_called_once()
    instance.update_forecast_hourly.assert_called_once()

    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {"entity_id": "weather.abc"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert instance.update_observation.call_count == 2
    assert instance.update_forecast.call_count == 2
    assert instance.update_forecast_hourly.call_count == 2


async def test_error_observation(
    hass: HomeAssistant, mock_simple_nws, no_sensor
) -> None:
    """Test error during update observation."""
    instance = mock_simple_nws.return_value
    # first update fails
    instance.update_observation.side_effect = aiohttp.ClientError

    entry = MockConfigEntry(
        domain=nws.DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    instance.update_observation.assert_called_once()

    state = hass.states.get("weather.abc")
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_new_config_entry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, no_sensor
) -> None:
    """Test the expected entities are created."""
    entry = MockConfigEntry(
        domain=nws.DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids("weather")) == 1
    entry = hass.config_entries.async_entries()[0]
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 1


@pytest.mark.parametrize(
    ("service"),
    [
        SERVICE_GET_FORECASTS,
    ],
)
async def test_forecast_service(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    mock_simple_nws,
    no_sensor,
    service: str,
) -> None:
    """Test multiple forecast."""
    instance = mock_simple_nws.return_value

    entry = MockConfigEntry(
        domain=nws.DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    instance.update_observation.assert_called_once()
    instance.update_forecast.assert_called_once()
    instance.update_forecast_hourly.assert_called_once()

    for forecast_type in ("twice_daily", "hourly"):
        response = await hass.services.async_call(
            WEATHER_DOMAIN,
            service,
            {
                "entity_id": "weather.abc",
                "type": forecast_type,
            },
            blocking=True,
            return_response=True,
        )
        assert response == snapshot

    # Calling the services should use cached data
    instance.update_observation.assert_called_once()
    instance.update_forecast.assert_called_once()
    instance.update_forecast_hourly.assert_called_once()

    # Trigger data refetch
    freezer.tick(nws.DEFAULT_SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert instance.update_observation.call_count == 2
    assert instance.update_forecast.call_count == 2
    assert instance.update_forecast_hourly.call_count == 2

    for forecast_type in ("twice_daily", "hourly"):
        response = await hass.services.async_call(
            WEATHER_DOMAIN,
            service,
            {
                "entity_id": "weather.abc",
                "type": forecast_type,
            },
            blocking=True,
            return_response=True,
        )
        assert response == snapshot

    # Calling the services should update the hourly forecast
    assert instance.update_observation.call_count == 2
    assert instance.update_forecast.call_count == 2
    assert instance.update_forecast_hourly.call_count == 2

    # third update fails, but data is cached
    instance.update_forecast_hourly.side_effect = aiohttp.ClientError
    freezer.tick(nws.DEFAULT_SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {
            "entity_id": "weather.abc",
            "type": "hourly",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot

    # after additional 35 minutes data caching expires, data is no longer shown
    freezer.tick(timedelta(minutes=35))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {
            "entity_id": "weather.abc",
            "type": "hourly",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


@pytest.mark.parametrize(
    ("forecast_type", "entity_id"),
    [("hourly", "weather.abc")],
)
async def test_forecast_subscription(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    mock_simple_nws,
    no_sensor,
    forecast_type: str,
    entity_id: str,
) -> None:
    """Test multiple forecast."""
    client = await hass_ws_client(hass)

    # Pre-create the hourly entity
    entity_registry.async_get_or_create(
        WEATHER_DOMAIN,
        nws.DOMAIN,
        "35_-75_hourly",
        suggested_object_id="abc_hourly",
    )

    entry = MockConfigEntry(
        domain=nws.DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

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

    freezer.tick(nws.DEFAULT_SCAN_INTERVAL + timedelta(seconds=1))
    await hass.async_block_till_done()
    msg = await client.receive_json()

    assert msg["id"] == subscription_id
    assert msg["type"] == "event"
    forecast2 = msg["event"]["forecast"]

    assert forecast2 != []
    assert forecast2 == snapshot


@pytest.mark.parametrize(
    ("forecast_type", "entity_id"),
    [("hourly", "weather.abc")],
)
async def test_forecast_subscription_with_failing_coordinator(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    mock_simple_nws_times_out,
    no_sensor,
    forecast_type: str,
    entity_id: str,
) -> None:
    """Test a forecast subscription when the coordinator is failing to update."""
    client = await hass_ws_client(hass)

    # Pre-create the hourly entity
    entity_registry.async_get_or_create(
        WEATHER_DOMAIN,
        nws.DOMAIN,
        "35_-75_hourly",
        suggested_object_id="abc_hourly",
    )

    entry = MockConfigEntry(
        domain=nws.DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await client.send_json_auto_id(
        {
            "type": "weather/subscribe_forecast",
            "forecast_type": forecast_type,
            "entity_id": entity_id,
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]

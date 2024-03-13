"""Test Met Éireann weather entity."""
import datetime

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.met_eireann import UPDATE_INTERVAL
from homeassistant.components.met_eireann.const import DOMAIN
from homeassistant.components.weather import (
    DOMAIN as WEATHER_DOMAIN,
    LEGACY_SERVICE_GET_FORECAST,
    SERVICE_GET_FORECASTS,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def setup_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Create a mock configuration for testing."""
    mock_data = MockConfigEntry(
        domain=DOMAIN,
        data={"name": "Somewhere", "latitude": 10, "longitude": 20, "elevation": 0},
    )
    mock_data.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_data.entry_id)
    await hass.async_block_till_done()
    return mock_data


async def test_new_config_entry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_weather
) -> None:
    """Test the expected entities are created."""
    await setup_config_entry(hass)
    assert len(hass.states.async_entity_ids("weather")) == 1

    entry = hass.config_entries.async_entries()[0]
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 1


async def test_legacy_config_entry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_weather
) -> None:
    """Test the expected entities are created."""
    entity_registry.async_get_or_create(
        WEATHER_DOMAIN,
        DOMAIN,
        "10-20-hourly",
    )
    await setup_config_entry(hass)
    assert len(hass.states.async_entity_ids("weather")) == 2

    entry = hass.config_entries.async_entries()[0]
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 2


async def test_weather(hass: HomeAssistant, mock_weather) -> None:
    """Test weather entity."""
    await setup_config_entry(hass)
    assert len(hass.states.async_entity_ids("weather")) == 1
    assert len(mock_weather.mock_calls) == 4

    # Test we do not track config
    await hass.config.async_update(latitude=10, longitude=20)
    await hass.async_block_till_done()

    assert len(mock_weather.mock_calls) == 4

    entry = hass.config_entries.async_entries()[0]
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids("weather")) == 0


@pytest.mark.parametrize(
    ("service"),
    [
        SERVICE_GET_FORECASTS,
        LEGACY_SERVICE_GET_FORECAST,
    ],
)
async def test_forecast_service(
    hass: HomeAssistant,
    mock_weather,
    snapshot: SnapshotAssertion,
    service: str,
) -> None:
    """Test multiple forecast."""
    mock_weather.get_forecast.return_value = [
        {
            "condition": "SleetSunThunder",
            "datetime": datetime.datetime(2023, 8, 8, 12, 0, tzinfo=datetime.UTC),
            "temperature": 10.0,
        },
        {
            "condition": "SleetSunThunder",
            "datetime": datetime.datetime(2023, 8, 9, 12, 0, tzinfo=datetime.UTC),
            "temperature": 20.0,
        },
    ]

    await setup_config_entry(hass)
    assert len(hass.states.async_entity_ids("weather")) == 1
    entity_id = hass.states.async_entity_ids("weather")[0]

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {
            "entity_id": entity_id,
            "type": "daily",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {
            "entity_id": entity_id,
            "type": "hourly",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


@pytest.mark.parametrize("forecast_type", ["daily", "hourly"])
async def test_forecast_subscription(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    mock_weather,
    snapshot: SnapshotAssertion,
    forecast_type: str,
) -> None:
    """Test multiple forecast."""
    client = await hass_ws_client(hass)

    mock_weather.get_forecast.return_value = [
        {
            "condition": "SleetSunThunder",
            "datetime": datetime.datetime(2023, 8, 8, 12, 0, tzinfo=datetime.UTC),
            "temperature": 10.0,
        },
        {
            "condition": "SleetSunThunder",
            "datetime": datetime.datetime(2023, 8, 9, 12, 0, tzinfo=datetime.UTC),
            "temperature": 20.0,
        },
    ]

    await setup_config_entry(hass)
    assert len(hass.states.async_entity_ids("weather")) == 1
    entity_id = hass.states.async_entity_ids("weather")[0]

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

    assert forecast1 == snapshot

    mock_weather.get_forecast.return_value = [
        {
            "condition": "SleetSunThunder",
            "datetime": datetime.datetime(2023, 8, 8, 12, 0, tzinfo=datetime.UTC),
            "temperature": 15.0,
        },
        {
            "condition": "SleetSunThunder",
            "datetime": datetime.datetime(2023, 8, 9, 12, 0, tzinfo=datetime.UTC),
            "temperature": 25.0,
        },
    ]

    freezer.tick(UPDATE_INTERVAL + datetime.timedelta(seconds=1))
    await hass.async_block_till_done()
    msg = await client.receive_json()

    assert msg["id"] == subscription_id
    assert msg["type"] == "event"
    forecast2 = msg["event"]["forecast"]

    assert forecast2 == snapshot

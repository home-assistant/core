"""Test Met weather entity."""

from homeassistant import config_entries
from homeassistant.components.met import DOMAIN
from homeassistant.components.weather import (
    ATTR_CONDITION_CLOUDY,
    ATTR_WEATHER_DEW_POINT,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_UV_INDEX,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED,
    DOMAIN as WEATHER_DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration


async def test_new_config_entry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_weather
) -> None:
    """Test the expected entities are created."""
    await hass.config_entries.flow.async_init("met", context={"source": "onboarding"})
    await hass.async_block_till_done()
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
        "home-hourly",
    )
    await hass.config_entries.flow.async_init("met", context={"source": "onboarding"})
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids("weather")) == 1

    entry = hass.config_entries.async_entries()[0]
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 1


async def test_weather(hass: HomeAssistant, mock_weather) -> None:
    """Test states of the weather."""

    await init_integration(hass)
    assert len(hass.states.async_entity_ids("weather")) == 1
    entity_id = hass.states.async_entity_ids("weather")[0]

    state = hass.states.get(entity_id)
    assert state
    assert state.state == ATTR_CONDITION_CLOUDY
    assert state.attributes[ATTR_WEATHER_TEMPERATURE] == 15
    assert state.attributes[ATTR_WEATHER_PRESSURE] == 100
    assert state.attributes[ATTR_WEATHER_HUMIDITY] == 50
    assert state.attributes[ATTR_WEATHER_WIND_SPEED] == 10
    assert state.attributes[ATTR_WEATHER_WIND_BEARING] == 90
    assert state.attributes[ATTR_WEATHER_DEW_POINT] == 12.1
    assert state.attributes[ATTR_WEATHER_UV_INDEX] == 1.1


async def test_tracking_home(hass: HomeAssistant, mock_weather) -> None:
    """Test we track home."""
    await hass.config_entries.flow.async_init("met", context={"source": "onboarding"})
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids("weather")) == 1
    assert len(mock_weather.mock_calls) == 4

    # Test we track config
    await hass.config.async_update(latitude=10, longitude=20)
    await hass.async_block_till_done()

    assert len(mock_weather.mock_calls) == 8

    # Same coordinates again should not trigger any new requests to met.no
    await hass.config.async_update(latitude=10, longitude=20)
    await hass.async_block_till_done()
    assert len(mock_weather.mock_calls) == 8

    entry = hass.config_entries.async_entries()[0]
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids("weather")) == 0


async def test_not_tracking_home(hass: HomeAssistant, mock_weather) -> None:
    """Test when we not track home."""

    await hass.config_entries.flow.async_init(
        "met",
        context={"source": config_entries.SOURCE_USER},
        data={"name": "Somewhere", "latitude": 10, "longitude": 20, "elevation": 0},
    )
    await hass.async_block_till_done()
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


async def test_remove_hourly_entity(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_weather
) -> None:
    """Test removing the hourly entity."""

    # Pre-create registry entry for disabled by default hourly weather
    entity_registry.async_get_or_create(
        WEATHER_DOMAIN,
        DOMAIN,
        "10-20-hourly",
        suggested_object_id="forecast_somewhere_hourly",
        disabled_by=None,
    )
    assert list(entity_registry.entities.keys()) == [
        "weather.forecast_somewhere_hourly"
    ]

    await hass.config_entries.flow.async_init(
        "met",
        context={"source": config_entries.SOURCE_USER},
        data={"name": "Somewhere", "latitude": 10, "longitude": 20, "elevation": 0},
    )
    await hass.async_block_till_done()
    assert hass.states.async_entity_ids("weather") == ["weather.forecast_somewhere"]
    assert list(entity_registry.entities.keys()) == ["weather.forecast_somewhere"]

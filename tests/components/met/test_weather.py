"""Test Met weather entity."""
from homeassistant import config_entries
from homeassistant.components.met import DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


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
    assert len(hass.states.async_entity_ids("weather")) == 2

    entry = hass.config_entries.async_entries()[0]
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 2


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

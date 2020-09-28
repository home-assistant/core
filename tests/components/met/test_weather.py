"""Test Met weather entity."""

from homeassistant.components.met import DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN


async def test_tracking_home(hass, mock_weather):
    """Test we track home."""
    await hass.config_entries.flow.async_init("met", context={"source": "onboarding"})
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids("weather")) == 1
    assert len(mock_weather.mock_calls) == 4

    # Test the hourly sensor is disabled by default
    registry = await hass.helpers.entity_registry.async_get_registry()

    state = hass.states.get("weather.test_home_hourly")
    assert state is None

    entry = registry.async_get("weather.test_home_hourly")
    assert entry
    assert entry.disabled
    assert entry.disabled_by == "integration"

    # Test we track config
    await hass.config.async_update(latitude=10, longitude=20)
    await hass.async_block_till_done()

    assert len(mock_weather.mock_calls) == 8

    entry = hass.config_entries.async_entries()[0]
    await hass.config_entries.async_remove(entry.entry_id)
    assert len(hass.states.async_entity_ids("weather")) == 0


async def test_not_tracking_home(hass, mock_weather):
    """Test when we not track home."""

    # Pre-create registry entry for disabled by default hourly weather
    registry = await hass.helpers.entity_registry.async_get_registry()
    registry.async_get_or_create(
        WEATHER_DOMAIN,
        DOMAIN,
        "10-20-hourly",
        suggested_object_id="somewhere_hourly",
        disabled_by=None,
    )

    await hass.config_entries.flow.async_init(
        "met",
        context={"source": "user"},
        data={"name": "Somewhere", "latitude": 10, "longitude": 20, "elevation": 0},
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids("weather")) == 2
    assert len(mock_weather.mock_calls) == 4

    # Test we do not track config
    await hass.config.async_update(latitude=10, longitude=20)
    await hass.async_block_till_done()

    assert len(mock_weather.mock_calls) == 4

    entry = hass.config_entries.async_entries()[0]
    await hass.config_entries.async_remove(entry.entry_id)
    assert len(hass.states.async_entity_ids("weather")) == 0

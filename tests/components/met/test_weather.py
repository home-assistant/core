"""Test Met weather entity."""
from homeassistant import config_entries
from homeassistant.components.met.const import DOMAIN
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME


async def test_tracking_home(hass, mock_weather):
    """Test we track home."""
    await hass.config_entries.flow.async_init(DOMAIN, context={"source": "onboarding"})
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids("weather")) == 1
    assert len(mock_weather.mock_calls) == 3

    # Test we track config
    await hass.config.async_update(latitude=10, longitude=20)
    await hass.async_block_till_done()

    assert len(mock_weather.mock_calls) == 6

    entry = hass.config_entries.async_entries()[0]
    await hass.config_entries.async_remove(entry.entry_id)
    assert len(hass.states.async_entity_ids("weather")) == 0


async def test_not_tracking_home(hass, mock_weather):
    """Test when we not track home."""
    config = {
        CONF_NAME: "Somewhere",
        CONF_LATITUDE: 10,
        CONF_LONGITUDE: 20,
        CONF_ELEVATION: 0,
    }

    hass.config.components.add(DOMAIN)
    config_entry = config_entries.ConfigEntry(
        1,
        DOMAIN,
        "Mock Title",
        config,
        "test",
        config_entries.CONN_CLASS_CLOUD_POLL,
        {},
    )
    await hass.config_entries.async_forward_entry_setup(config_entry, "weather")
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids("weather")) == 1
    assert len(mock_weather.mock_calls) == 3

    # Test we do not track config
    await hass.config.async_update(latitude=10, longitude=20)
    await hass.async_block_till_done()

    assert len(mock_weather.mock_calls) == 3

    await hass.config_entries.async_forward_entry_unload(config_entry, "weather")
    assert len(hass.states.async_entity_ids("weather")) == 0

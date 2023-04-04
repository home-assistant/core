"""Test Met Éireann weather entity."""
from homeassistant.components.met_eireann.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_weather(hass: HomeAssistant, mock_weather) -> None:
    """Test weather entity."""
    # Create a mock configuration for testing
    mock_data = MockConfigEntry(
        domain=DOMAIN,
        data={"name": "Somewhere", "latitude": 10, "longitude": 20, "elevation": 0},
    )
    mock_data.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_data.entry_id)
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

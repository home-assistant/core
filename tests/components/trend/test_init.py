"""Test the Trend integration."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.trend.conftest import ComponentSetup


async def test_setup_and_remove_config_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test setting up and removing a config entry."""
    registry = er.async_get(hass)
    trend_entity_id = "binary_sensor.my_trend"

    # Set up the config entry
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the entity is registered in the entity registry
    assert registry.async_get(trend_entity_id) is not None

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert hass.states.get(trend_entity_id) is None
    assert registry.async_get(trend_entity_id) is None


async def test_reload_config_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    setup_component: ComponentSetup,
) -> None:
    """Test config entry reload."""
    await setup_component({})

    assert config_entry.state is ConfigEntryState.LOADED

    assert hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, "max_samples": 4.0}
    )

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.data == {**config_entry.data, "max_samples": 4.0}

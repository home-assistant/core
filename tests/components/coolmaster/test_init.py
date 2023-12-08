"""The test for the Coolmaster integration."""
from homeassistant.components.coolmaster.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_load_entry(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test Coolmaster initial load."""
    # 2 units times 4 entities (climate, binary_sensor, sensor, button).
    assert hass.states.async_entity_ids_count() == 8
    assert load_int.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test Coolmaster unloading an entry."""
    assert load_int.entry_id in hass.data.get(DOMAIN)
    await hass.config_entries.async_unload(load_int.entry_id)
    await hass.async_block_till_done()
    assert load_int.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)

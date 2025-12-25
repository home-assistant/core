"""Test the System Nexa 2 switch platform."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_switch_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_system_nexa_2_device,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the switch entities."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check that the relay switch is created
    state = hass.states.get("switch.test_device_relay")
    assert state is not None
    # Entity is unavailable until coordinator receives data
    assert state.state == "unavailable"

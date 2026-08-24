"""Test the my-PV entity."""

from unittest.mock import AsyncMock

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_entity_unavailable_not_connected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test if an entity is unavailable when not connected."""

    mock_config_entry.add_to_hass(hass)

    mock_my_pv_client.connected = False

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.state == STATE_UNAVAILABLE


async def test_entity_unavailable_data_value_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test if an entity is unavailable when data value is None."""

    mock_config_entry.add_to_hass(hass)

    mock_my_pv_client.get_data_value.return_value = None

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.state == STATE_UNAVAILABLE

"""Test the my-PV entity."""

from unittest.mock import AsyncMock, Mock

from my_pv.exceptions import MyPVNotSupportedError

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_entity_heater_unavailable_not_connected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test if an entity is unavailable when not connected."""

    mock_config_entry.add_to_hass(hass)

    mock_my_pv_client.get_setup_configuration = Mock(
        return_value={"step": 0.1, "unit": "°C", "min": 5.0, "max": 95.0}
    )
    mock_my_pv_client.connected = False

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.state == STATE_UNAVAILABLE


async def test_entity_heater_unavailable_data_value_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test if an entity is unavailable when data value is None."""

    mock_config_entry.add_to_hass(hass)

    mock_my_pv_client.get_setup_configuration = Mock(
        return_value={"step": 0.1, "unit": "°C", "min": 5.0, "max": 95.0}
    )
    mock_my_pv_client.get_data_value.return_value = None

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.state == STATE_UNAVAILABLE


async def test_entity_heater_unavailable_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test if an entity is unavailable when data key is not supported."""

    mock_config_entry.add_to_hass(hass)

    mock_my_pv_client.get_setup_configuration = Mock(
        return_value={"step": 0.1, "unit": "°C", "min": 5.0, "max": 95.0}
    )
    mock_my_pv_client.get_data_value.side_effect = MyPVNotSupportedError()

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("water_heater.my_pv_ac_elwa_2")
    assert state.state == STATE_UNAVAILABLE

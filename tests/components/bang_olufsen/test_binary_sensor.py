"""Test the bang_olufsen binary sensor entities."""

from unittest.mock import AsyncMock

from mozart_api.models import BatteryState

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from .conftest import mock_websocket_connection
from .const import TEST_BATTERY, TEST_BATTERY_CHARGING_BINARY_SENSOR_ENTITY_ID

from tests.common import MockConfigEntry


async def test_battery_charging(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_mozart_client: AsyncMock,
    mock_config_entry_a5: MockConfigEntry,
) -> None:
    """Test the battery charging time entity."""
    # Ensure battery entities are created
    mock_mozart_client.get_battery_state.return_value = TEST_BATTERY

    # Load entry
    mock_config_entry_a5.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_a5.entry_id)
    await mock_websocket_connection(hass, mock_mozart_client)
    await hass.async_block_till_done()

    # Initial state is False
    assert (states := hass.states.get(TEST_BATTERY_CHARGING_BINARY_SENSOR_ENTITY_ID))
    assert states.state == STATE_OFF

    # Check binary sensor reacts as expected to WebSocket events
    battery_callback = mock_mozart_client.get_battery_notifications.call_args[0][0]

    battery_callback(BatteryState(is_charging=True))
    await hass.async_block_till_done()

    assert (states := hass.states.get(TEST_BATTERY_CHARGING_BINARY_SENSOR_ENTITY_ID))
    assert states.state == STATE_ON

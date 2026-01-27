"""Test the bang_olufsen sensor entities."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from mozart_api.models import PairedRemote, PairedRemoteResponse

from homeassistant.components.bang_olufsen.sensor import SCAN_INTERVAL
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import mock_websocket_connection
from .const import (
    TEST_BATTERY,
    TEST_BATTERY_SENSOR_ENTITY_ID,
    TEST_REMOTE_BATTERY_LEVEL_SENSOR_ENTITY_ID,
    TEST_REMOTE_SERIAL,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_battery_level(
    hass: HomeAssistant,
    mock_mozart_client: AsyncMock,
    mock_config_entry_a5: MockConfigEntry,
) -> None:
    """Test the battery level entity."""
    # Ensure battery entities are created
    mock_mozart_client.get_battery_state.return_value = TEST_BATTERY

    # Load entry
    mock_config_entry_a5.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_a5.entry_id)
    # Deliberately avoid triggering a battery notification

    assert (states := hass.states.get(TEST_BATTERY_SENSOR_ENTITY_ID))
    assert states.state is STATE_UNKNOWN

    # Check sensor reacts as expected to WebSocket events
    await mock_websocket_connection(hass, mock_mozart_client)

    assert (states := hass.states.get(TEST_BATTERY_SENSOR_ENTITY_ID))
    assert states.state == str(TEST_BATTERY.battery_level)


async def test_remote_battery_level(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    integration: None,
    mock_config_entry: MockConfigEntry,
    mock_mozart_client: AsyncMock,
) -> None:
    """Test the remote battery level entity."""

    # Check the default value is set
    assert (states := hass.states.get(TEST_REMOTE_BATTERY_LEVEL_SENSOR_ENTITY_ID))
    assert states.state == "50"

    # Change battery level
    mock_mozart_client.get_bluetooth_remotes.return_value = PairedRemoteResponse(
        items=[
            PairedRemote(
                address="",
                app_version="1.0.0",
                battery_level=45,
                connected=True,
                serial_number=TEST_REMOTE_SERIAL,
                name="BEORC",
            )
        ]
    )

    # Trigger poll update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (states := hass.states.get(TEST_REMOTE_BATTERY_LEVEL_SENSOR_ENTITY_ID))
    assert states.state == "45"

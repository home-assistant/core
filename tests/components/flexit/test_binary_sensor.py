"""Test the Flexit binary sensor platform."""

from unittest.mock import patch

from modbus_connection.mock import MockModbusUnit
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


async def test_binary_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test Flexit binary sensor states."""
    mock_modbus_unit.holding.update({8: 215, 17: 2})
    mock_modbus_unit.input.update(
        {
            8: 120,
            9: 200,
            11: 50,
            13: 0,
            14: 0,
            15: 0,
            27: 1,
            28: 1,
            48: 0,
        }
    )
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.flexit._PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

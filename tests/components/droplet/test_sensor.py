"""Test Droplet sensors."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_droplet_discovery: AsyncMock,
    mock_droplet_connection: AsyncMock,
    mock_droplet: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Droplet sensors."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensors_update_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_droplet_discovery: AsyncMock,
    mock_droplet_connection: AsyncMock,
    mock_droplet: AsyncMock,
) -> None:
    """Test Droplet async update data."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.mock_title_flow_rate").state == "0.0264172052358148"

    mock_droplet.get_flow_rate.return_value = 0.5

    mock_droplet.listen_forever.call_args_list[0][0][1]({})

    assert hass.states.get("sensor.mock_title_flow_rate").state == "0.132086026179074"

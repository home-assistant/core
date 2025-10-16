"""Test the Nederlandse Spoorwegen sensor."""

from unittest.mock import AsyncMock

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.freeze_time("2025-09-15 14:30:00+00:00")
async def test_binary_sensor(
    hass: HomeAssistant,
    mock_nsapi,
    mock_config_entry: MockConfigEntry,
    mock_binary_sensor_platform,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor initialization."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_with_api_connection_error(
    hass: HomeAssistant,
    mock_nsapi: AsyncMock,
    mock_binary_sensor_platform,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor behavior when API connection fails."""
    # Make API calls fail from the start
    mock_nsapi.get_trips.side_effect = RequestsConnectionError("Connection failed")

    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    # Sensors should not be created at all if initial API call fails
    sensor_states = hass.states.async_all("binary_sensor")
    assert len(sensor_states) == 0

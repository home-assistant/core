"""Test the Nederlandse Spoorwegen binary sensor."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def mock_binary_sensor_platform() -> Generator:
    """Override PLATFORMS for NS integration."""
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ) as mock_platform:
        yield mock_platform


@pytest.mark.freeze_time("2025-09-15 14:30:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensor(
    hass: HomeAssistant,
    mock_nsapi: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor initialization."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.freeze_time("2025-09-15 14:30:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_no_upcoming_trips(
    hass: HomeAssistant,
    mock_nsapi: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor initialization."""
    mock_nsapi.get_trips.return_value = []
    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("binary_sensor.to_work_departure_delayed").state
        == STATE_UNKNOWN
    )


async def test_sensor_with_api_connection_error(
    hass: HomeAssistant,
    mock_nsapi: AsyncMock,
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

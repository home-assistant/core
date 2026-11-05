"""Test the Foreca sensor platform."""

from unittest.mock import MagicMock, patch

from pyforeca import CurrentWeather
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration


@pytest.mark.usefixtures("mock_foreca_client")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the states of the sensors."""
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensors_without_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
) -> None:
    """Test sensors are unknown when the API leaves their value out."""
    mock_foreca_client.current.return_value = CurrentWeather()
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

    states = hass.states.async_all(Platform.SENSOR)
    assert len(states) == 3
    assert {state.state for state in states} == {STATE_UNKNOWN}

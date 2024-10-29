"""Test Suez_water sensor platform."""

from unittest.mock import AsyncMock, patch

from syrupy import SnapshotAssertion

from homeassistant.components.suez_water import PySuezError, SuezClient
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_suez_sensors_valid_state_update(
    hass: HomeAssistant,
    suez_client,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that suez_water sensor plaform is loaded and in a valid state.

    Always one entity with required values, as provided by the library
    """
    with patch("homeassistant.components.suez_water.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(mock_config_entry, hass)

        assert mock_config_entry.state is ConfigEntryState.LOADED
        await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry
) -> None:
    """Test that the state of the entity reflect failure."""

    mock = AsyncMock(spec=SuezClient)
    mock.update.side_effect = PySuezError("Should fail to update")
    mock.check_credentials.return_value = True
    with (
        patch("homeassistant.components.suez_water.PLATFORMS", [Platform.SENSOR]),
        patch(
            "homeassistant.components.suez_water.SuezClient", return_value=mock
        ) as mock_client,
    ):
        await setup_integration(mock_client, mock_config_entry, hass)

        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

        state = hass.states.get("sensor.suez_mock_device_water_usage_yesterday")
        assert state is None

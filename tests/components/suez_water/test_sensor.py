"""Test init of Suez water component."""

from unittest.mock import AsyncMock, patch

from syrupy import SnapshotAssertion

from homeassistant.components.suez_water import PySuezError, SuezClient
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


async def test_init_success(
    suez_client,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that the entry is loaded and has valid state."""
    with patch("homeassistant.components.suez_water.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(suez_client, config_entry, hass)

        assert config_entry.state is ConfigEntryState.LOADED
        entity_entries = er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )

        assert entity_entries
        assert len(entity_entries) == 1
        for entity_entry in entity_entries:
            assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
            assert hass.states.get(entity_entry.entity_id) == snapshot(
                name=f"{entity_entry.entity_id}-state"
            )


async def test_update_failed(
    config_entry: MockConfigEntry, hass: HomeAssistant
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
        await setup_integration(mock_client, config_entry, hass)

        assert config_entry.state is ConfigEntryState.SETUP_RETRY

        state = hass.states.get("sensor.suez_mock_device_water_usage_yesterday")
        assert state is None

"""Verify entry setup, retry and unload behavior."""

from unittest.mock import AsyncMock

from dobiss_nxt import DobissAuthenticationError, DobissConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er


async def test_setup_unload(
    hass: HomeAssistant, mock_entry: MockConfigEntry, mock_client: AsyncMock
) -> None:
    """Set up both lights and unload their shared coordinator."""
    mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("light.kitchen") is not None
    assert await hass.config_entries.async_unload(mock_entry.entry_id)
    assert mock_entry.state is ConfigEntryState.NOT_LOADED


async def test_existing_entity_keeps_id(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Moving an output to its own device preserves existing dashboard references."""
    mock_entry.add_to_hass(hass)
    controller = device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        identifiers={("dobiss", mock_entry.entry_id)},
        name="Dobiss (192.168.0.20)",
    )
    registry = entity_registry
    entity = registry.async_get_or_create(
        "light",
        "dobiss",
        f"{mock_entry.entry_id}_4_0",
        suggested_object_id="dobiss_kitchen",
        config_entry=mock_entry,
        device_id=controller.id,
        has_entity_name=True,
        original_name="Kitchen",
    )
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(entity.entity_id)
    assert state.attributes["friendly_name"] == "Kitchen"
    updated = registry.async_get(entity.entity_id)
    assert updated.device_id != controller.id
    output = device_registry.async_get(updated.device_id)
    assert output.name == "Kitchen"
    assert output.via_device_id == controller.id


@pytest.mark.parametrize(
    ("method", "error", "state"),
    [
        ("discover_lights", DobissConnectionError, ConfigEntryState.SETUP_RETRY),
        ("light_states", DobissConnectionError, ConfigEntryState.SETUP_RETRY),
        ("discover_lights", DobissAuthenticationError, ConfigEntryState.SETUP_ERROR),
        ("light_states", DobissAuthenticationError, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: AsyncMock,
    method: str,
    error: type[Exception],
    state: ConfigEntryState,
) -> None:
    """Treat unreachable controllers as retryable and credentials as auth failures."""
    getattr(mock_client, method).side_effect = error
    mock_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.state is state

"""Test the Flic Button number platform."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.flic_button.const import (
    CONF_PUSH_TWIST_MODE,
    DOMAIN,
    PushTwistMode,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Return list of platforms to test."""
    return [Platform.NUMBER]


async def test_twist_default_mode_creates_two_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_twist_config_entry: MockConfigEntry,
    mock_twist_coordinator: MagicMock,
    mock_twist_ble_device_from_address: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test DEFAULT mode creates twist_position and push_twist_position entities."""
    # DEFAULT mode (no options set = default)
    mock_twist_coordinator.get_slot_value = MagicMock(return_value=0.0)
    mock_twist_coordinator.set_slot_value = MagicMock()
    mock_twist_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.flic_button.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_twist_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_twist_config_entry.state is ConfigEntryState.LOADED

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_twist_config_entry.entry_id
    )
    number_entities = [e for e in entities if e.domain == "number"]

    # Should have exactly 2 number entities in DEFAULT mode
    assert len(number_entities) == 2

    unique_ids = {e.unique_id for e in number_entities}
    assert f"{mock_twist_coordinator.client.address}-twist-position" in unique_ids
    assert f"{mock_twist_coordinator.client.address}-push-twist-position" in unique_ids


async def test_twist_selector_mode_creates_twelve_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_twist_config_entry: MockConfigEntry,
    mock_twist_coordinator: MagicMock,
    mock_twist_ble_device_from_address: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test SELECTOR mode creates 12 per-slot number entities."""
    mock_twist_coordinator.get_slot_value = MagicMock(return_value=0.0)
    mock_twist_coordinator.set_slot_value = MagicMock()

    # Create a new config entry with SELECTOR mode in options
    selector_config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=mock_twist_config_entry.title,
        unique_id=mock_twist_config_entry.unique_id,
        data=dict(mock_twist_config_entry.data),
        options={CONF_PUSH_TWIST_MODE: PushTwistMode.SELECTOR},
    )
    selector_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.flic_button.PLATFORMS", platforms):
        await hass.config_entries.async_setup(selector_config_entry.entry_id)
        await hass.async_block_till_done()

    assert selector_config_entry.state is ConfigEntryState.LOADED

    entities = er.async_entries_for_config_entry(
        entity_registry, selector_config_entry.entry_id
    )
    number_entities = [e for e in entities if e.domain == "number"]

    # Should have exactly 12 number entities in SELECTOR mode
    assert len(number_entities) == 12

    unique_ids = {e.unique_id for e in number_entities}
    for i in range(12):
        assert f"{mock_twist_coordinator.client.address}-slot-{i}" in unique_ids


async def test_twist_default_mode_integer_step(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_twist_config_entry: MockConfigEntry,
    mock_twist_coordinator: MagicMock,
    mock_twist_ble_device_from_address: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test DEFAULT mode number entities use integer step of 1."""
    mock_twist_coordinator.get_slot_value = MagicMock(return_value=0.0)
    mock_twist_coordinator.set_slot_value = MagicMock()
    mock_twist_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.flic_button.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_twist_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_twist_config_entry.state is ConfigEntryState.LOADED

    # Both entities should have integer values (0, not 0.0)
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_twist_config_entry.entry_id
    )
    number_entities = [e for e in entities if e.domain == "number"]
    assert len(number_entities) == 2

    # Verify values are integers by checking entity states
    for entity_entry in number_entities:
        state = hass.states.get(entity_entry.entity_id)
        if state is not None:
            # The state value should be "0" not "0.0"
            assert state.state == "0"


async def test_flic2_no_number_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test Flic 2 devices create no number entities."""
    entities = er.async_entries_for_config_entry(
        entity_registry, init_integration.entry_id
    )
    number_entities = [e for e in entities if e.domain == "number"]
    assert len(number_entities) == 0


async def test_duo_creates_dial_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_duo_config_entry: MockConfigEntry,
    mock_duo_coordinator: MagicMock,
    mock_duo_ble_device_from_address: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test Duo devices create 2 dial number entities."""
    mock_duo_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.flic_button.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_duo_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_duo_config_entry.state is ConfigEntryState.LOADED

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_duo_config_entry.entry_id
    )
    number_entities = [e for e in entities if e.domain == "number"]

    # Should have exactly 2 dial entities for Duo
    assert len(number_entities) == 2

    unique_ids = {e.unique_id for e in number_entities}
    assert f"{mock_duo_coordinator.client.address}-duo-dial-0" in unique_ids
    assert f"{mock_duo_coordinator.client.address}-duo-dial-1" in unique_ids

"""Tests for the Tewke number platform."""

from unittest.mock import AsyncMock, patch
import pytest

from pytewke import EnergyOverrideData
from pytewke.error import (
    PyTewkeCoapError,
    PyTewkeInvalidRequestError,
    PyTewkeUnknownError,
)

from homeassistant.components.number import ATTR_VALUE, DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_number_platform(
    hass: HomeAssistant, mock_tap: AsyncMock, mock_config_entry: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """Test number platform setup and setting values."""
    entity_registry.async_get_or_create(
        NUMBER_DOMAIN,
        "tewke",
        "test_dock_id_energy_override",
        suggested_object_id="living_room_tewke_switch_energy_override",
        disabled_by=None,
    )
    mock_tap.get_energy_override.return_value = EnergyOverrideData(
        active=True, override=42.5
    )
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "number.living_room_tewke_switch_energy_override"
    
    # State should be 42.5
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "42.5"

    # Set value to 0
    mock_tap.set_energy_override.return_value = EnergyOverrideData(
        active=False, override=0.0
    )
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 0.0},
        blocking=True,
    )
    
    mock_tap.set_energy_override.assert_called_once_with(None)
    
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unknown"  # when inactive, native_value returns None, which maps to "unknown"

    # Set value > 0
    mock_tap.set_energy_override.reset_mock()
    mock_tap.set_energy_override.return_value = EnergyOverrideData(
        active=True, override=10.0
    )
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 10.0},
        blocking=True,
    )
    
    mock_tap.set_energy_override.assert_called_once_with(10.0)
    
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "10.0"


@pytest.mark.parametrize(
    ("exception", "expected_message"),
    [
        (PyTewkeInvalidRequestError("test"), "Internal error setting energy override"),
        (RuntimeError("test"), "Internal error setting energy override"),
        (TimeoutError("test"), "Setting energy override timed out"),
        (PyTewkeCoapError("test", None), "Error setting energy override"),
        (PyTewkeUnknownError("test"), "Error setting energy override"),
    ],
)
async def test_number_set_value_exceptions(
    hass: HomeAssistant,
    mock_tap: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    exception: Exception,
    expected_message: str,
) -> None:
    """Test exceptions when setting number value."""
    entity_registry.async_get_or_create(
        NUMBER_DOMAIN,
        "tewke",
        "test_dock_id_energy_override",
        suggested_object_id="living_room_tewke_switch_energy_override",
        disabled_by=None,
    )
    mock_tap.get_energy_override.return_value = EnergyOverrideData(
        active=True, override=42.5
    )
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "number.living_room_tewke_switch_energy_override"
    mock_tap.set_energy_override.side_effect = exception

    with pytest.raises(HomeAssistantError, match=expected_message):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 10.0},
            blocking=True,
        )


async def test_number_inactive(
    hass: HomeAssistant, mock_tap: AsyncMock, mock_config_entry: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """Test number entity when energy override is inactive."""
    entity_registry.async_get_or_create(
        NUMBER_DOMAIN,
        "tewke",
        "test_dock_id_energy_override",
        suggested_object_id="living_room_tewke_switch_energy_override",
        disabled_by=None,
    )
    mock_tap.get_energy_override.return_value = EnergyOverrideData(
        active=False, override=0.0
    )
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "number.living_room_tewke_switch_energy_override"
    
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unknown"


async def test_number_setup_none(
    hass: HomeAssistant, mock_tap: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test number entity is not created if get_energy_override returns None."""
    mock_tap.get_energy_override.return_value = None
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "number.living_room_tewke_switch_energy_override"
    
    state = hass.states.get(entity_id)
    assert state is None

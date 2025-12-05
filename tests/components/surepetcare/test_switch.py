"""Tests for Sure PetCare switches."""

from unittest.mock import AsyncMock, patch

import pytest
from surepy.const import BASE_RESOURCE
from surepy.exceptions import SurePetcareError

from homeassistant.components.surepetcare.const import PROFILE_INDOOR, PROFILE_OUTDOOR
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import MOCK_CAT_FLAP, MOCK_PET, MOCK_PET_FLAP
from .helpers import call_switch_turn_off, call_switch_turn_on

from tests.common import MockConfigEntry


async def test_switch_turn_on(
    hass: HomeAssistant,
    surepetcare,
    mock_config_entry_setup: MockConfigEntry,
) -> None:
    """Test turning on the switch (setting indoor mode)."""
    entity_id = "switch.pet_flap_pet_indoor_only_mode"

    # Initial state should be OFF (profile 2 = outdoor)
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Mock the API call through the fixture
    surepetcare.call = AsyncMock(
        return_value={
            "data": {
                "id": MOCK_PET["tag_id"],
                "device_id": MOCK_PET_FLAP["id"],
                "profile": PROFILE_INDOOR,
            }
        }
    )

    await call_switch_turn_on(hass, entity_id)

    surepetcare.call.assert_called_once_with(
        method="PUT",
        resource=f"{BASE_RESOURCE}/device/{MOCK_PET_FLAP['id']}/tag/{MOCK_PET['tag_id']}",
        json={"profile": PROFILE_INDOOR},
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_switch_turn_off(
    hass: HomeAssistant,
    surepetcare,
    mock_config_entry_setup: MockConfigEntry,
) -> None:
    """Test turning off the switch (setting outdoor mode)."""
    entity_id = "switch.cat_flap_pet_indoor_only_mode"

    # Initial state should be ON (profile 3 = indoor)
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    # Mock the API call through the fixture
    surepetcare.call = AsyncMock(
        return_value={
            "data": {
                "id": MOCK_PET["tag_id"],
                "device_id": MOCK_CAT_FLAP["id"],
                "profile": PROFILE_OUTDOOR,
            }
        }
    )

    await call_switch_turn_off(hass, entity_id)

    surepetcare.call.assert_called_once_with(
        method="PUT",
        resource=f"{BASE_RESOURCE}/device/{MOCK_CAT_FLAP['id']}/tag/{MOCK_PET['tag_id']}",
        json={"profile": PROFILE_OUTDOOR},
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_switch_turn_on_already_on(
    hass: HomeAssistant,
    surepetcare,
    mock_config_entry_setup: MockConfigEntry,
) -> None:
    """Test turning on a switch that's already on (no redundant API call)."""
    entity_id = "switch.cat_flap_pet_indoor_only_mode"

    # Initial state should be ON (profile 3 = indoor)
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    # Mock the API call to track it's not called
    surepetcare.call = AsyncMock()

    await call_switch_turn_on(hass, entity_id)
    surepetcare.call.assert_not_called()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_switch_turn_off_already_off(
    hass: HomeAssistant,
    surepetcare,
    mock_config_entry_setup: MockConfigEntry,
) -> None:
    """Test turning off a switch that's already off (no redundant API call)."""
    entity_id = "switch.pet_flap_pet_indoor_only_mode"

    # Initial state should be OFF (profile 2 = outdoor)
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Mock the API call to track it's not called
    surepetcare.call = AsyncMock()

    await call_switch_turn_off(hass, entity_id)
    surepetcare.call.assert_not_called()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_switch_turn_on_api_error(
    hass: HomeAssistant,
    surepetcare,
    mock_config_entry_setup: MockConfigEntry,
) -> None:
    """Test error handling when API call fails during turn_on."""
    entity_id = "switch.pet_flap_pet_indoor_only_mode"

    # Initial state should be OFF (profile 2 = outdoor)
    initial_state = hass.states.get(entity_id)
    assert initial_state.state == STATE_OFF

    # Mock the API call to raise an error
    surepetcare.call = AsyncMock(side_effect=SurePetcareError("Test API error"))

    # Mock coordinator refresh to verify it's called on error
    with patch(
        "homeassistant.components.surepetcare.coordinator.SurePetcareDataCoordinator.async_request_refresh",
        new=AsyncMock(),
    ) as mock_refresh:
        with pytest.raises(SurePetcareError, match="Test API error"):
            await call_switch_turn_on(hass, entity_id)

        mock_refresh.assert_called_once()

    # State should rollback to OFF after error
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_switch_turn_off_api_error(
    hass: HomeAssistant,
    surepetcare,
    mock_config_entry_setup: MockConfigEntry,
) -> None:
    """Test error handling when API call fails during turn_off."""
    entity_id = "switch.cat_flap_pet_indoor_only_mode"

    # Initial state should be ON (profile 3 = indoor)
    initial_state = hass.states.get(entity_id)
    assert initial_state.state == STATE_ON

    # Mock the API call to raise an error
    surepetcare.call = AsyncMock(side_effect=SurePetcareError("Test API error"))

    # Mock coordinator refresh to verify it's called on error
    with patch(
        "homeassistant.components.surepetcare.coordinator.SurePetcareDataCoordinator.async_request_refresh",
        new=AsyncMock(),
    ) as mock_refresh:
        with pytest.raises(SurePetcareError, match="Test API error"):
            await call_switch_turn_off(hass, entity_id)

        mock_refresh.assert_called_once()

    # State should rollback to ON after error
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

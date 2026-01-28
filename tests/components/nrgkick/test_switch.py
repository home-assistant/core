"""Tests for the NRGkick switch platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, call

from nrgkick_api import NRGkickCommandRejectedError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

pytestmark = pytest.mark.usefixtures("entity_registry_enabled_by_default")


async def test_switch_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test switch entities."""
    await setup_integration(hass, mock_config_entry, platforms=[Platform.SWITCH])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_charge_switch_service_calls_update_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the charge switch calls the API and updates state."""
    await setup_integration(hass, mock_config_entry, platforms=[Platform.SWITCH])

    async def set_charge_pause(pause: bool) -> int:
        return 1 if pause else 0

    mock_nrgkick_api.set_charge_pause.side_effect = set_charge_pause

    entity_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.domain == "switch" and entry.translation_key == "charging_enabled"
    )
    entity_id = entity_entry.entity_id

    assert (state := hass.states.get(entity_id))
    assert state.state == "on"

    # Pause charging
    mock_nrgkick_api.get_control.return_value["charge_pause"] = 1
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )

    # Resume charging
    mock_nrgkick_api.get_control.return_value["charge_pause"] = 0
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )

    assert mock_nrgkick_api.set_charge_pause.await_args_list == [
        call(True),
        call(False),
    ]
    assert (state := hass.states.get(entity_id))
    assert state.state == "on"


async def test_charge_switch_rejected_by_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the switch surfaces device rejection messages and keeps state."""
    await setup_integration(hass, mock_config_entry, platforms=[Platform.SWITCH])

    entity_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.domain == "switch" and entry.translation_key == "charging_enabled"
    )
    entity_id = entity_entry.entity_id

    # Device refuses the command and the library raises an exception.
    mock_nrgkick_api.set_charge_pause.side_effect = NRGkickCommandRejectedError(
        "Charging pause is blocked by solar-charging"
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": entity_id},
            blocking=True,
        )

    assert "blocked by solar-charging" in str(err.value)

    # State should reflect actual device control data (still not paused).
    assert (state := hass.states.get(entity_id))
    assert state.state == "on"

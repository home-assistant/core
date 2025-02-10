"""Tests for the TechnoVE switch platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion
from technove import TechnoVEConnectionError, TechnoVEError

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_technove")
async def test_switches(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the creation and values of the TechnoVE switches."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SWITCH])

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert (state := hass.states.get(entity_entry.entity_id))
        assert state == snapshot(name=f"{entity_entry.entity_id}-state")


@pytest.mark.parametrize(
    ("entity_id", "method", "called_with_on", "called_with_off"),
    [
        (
            "switch.technove_station_auto_charge",
            "set_auto_charge",
            {"enabled": True},
            {"enabled": False},
        ),
        (
            "switch.technove_station_charging_enabled",
            "set_charging_enabled",
            {"enabled": True},
            {"enabled": False},
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_switch_on_off(
    hass: HomeAssistant,
    mock_technove: MagicMock,
    entity_id: str,
    method: str,
    called_with_on: dict[str, bool | int],
    called_with_off: dict[str, bool | int],
) -> None:
    """Test on/off services."""
    state = hass.states.get(entity_id)
    method_mock = getattr(mock_technove, method)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: state.entity_id},
        blocking=True,
    )

    assert method_mock.call_count == 1
    method_mock.assert_called_with(**called_with_on)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: state.entity_id},
        blocking=True,
    )

    assert method_mock.call_count == 2
    method_mock.assert_called_with(**called_with_off)


@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        (
            "switch.technove_station_auto_charge",
            "set_auto_charge",
        ),
        (
            "switch.technove_station_charging_enabled",
            "set_charging_enabled",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_invalid_response(
    hass: HomeAssistant,
    mock_technove: MagicMock,
    entity_id: str,
    method: str,
) -> None:
    """Test invalid response, not becoming unavailable."""
    state = hass.states.get(entity_id)
    method_mock = getattr(mock_technove, method)

    method_mock.side_effect = TechnoVEError
    with pytest.raises(HomeAssistantError, match="Invalid response from TechnoVE API"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: state.entity_id},
            blocking=True,
        )

    assert method_mock.call_count == 1
    assert (state := hass.states.get(state.entity_id))
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        (
            "switch.technove_station_auto_charge",
            "set_auto_charge",
        ),
        (
            "switch.technove_station_charging_enabled",
            "set_charging_enabled",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_connection_error(
    hass: HomeAssistant,
    mock_technove: MagicMock,
    entity_id: str,
    method: str,
) -> None:
    """Test connection error, leading to becoming unavailable."""
    state = hass.states.get(entity_id)
    method_mock = getattr(mock_technove, method)

    method_mock.side_effect = TechnoVEConnectionError
    with pytest.raises(
        HomeAssistantError, match="Error communicating with TechnoVE API"
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: state.entity_id},
            blocking=True,
        )

    assert method_mock.call_count == 1
    assert (state := hass.states.get(state.entity_id))
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_disable_charging_auto_charge(
    hass: HomeAssistant,
    mock_technove: MagicMock,
) -> None:
    """Test failure to disable charging when the station is in auto charge mode."""
    entity_id = "switch.technove_station_charging_enabled"
    state = hass.states.get(entity_id)

    # Enable auto-charge mode
    device = mock_technove.update.return_value
    device.info.auto_charge = True

    with pytest.raises(
        ServiceValidationError,
        match="auto-charge is enabled",
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert (state := hass.states.get(state.entity_id))
    assert state.state != STATE_UNAVAILABLE

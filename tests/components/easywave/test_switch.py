"""Tests for the Easywave switch platform."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.easywave.const import (
    CONF_ENTRY_TYPE,
    CONF_GATEWAY_INDEX,
    CONF_GATEWAY_SERIAL,
    CONF_RECEIVER_KIND,
    DOMAIN,
    ENTRY_TYPE_RECEIVER,
    RECEIVER_KIND_SWITCH,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_ENTRY_DATA, MOCK_GATEWAY_SERIAL

from tests.common import MockConfigEntry

MOCK_SUBENTRY_ID = "receiver_subentry_test"


def _get_switch_entity_id(hass: HomeAssistant) -> str:
    """Look up the switch entity_id via unique_id in the entity registry."""
    unique_id = f"{MOCK_SUBENTRY_ID}_switch"
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("switch", DOMAIN, unique_id)
    assert entity_id is not None, f"No switch entity for unique_id {unique_id}"
    return entity_id


def _make_gateway(receiver_kind: str = RECEIVER_KIND_SWITCH) -> MockConfigEntry:
    """Return a gateway entry with a receiver subentry."""
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Easywave Gateway",
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options={
            "devices": [
                {
                    "id": MOCK_SUBENTRY_ID,
                    "title": "Test Receiver",
                    "unique_id": f"receiver_{MOCK_GATEWAY_SERIAL}_0",
                    "data": {
                        CONF_ENTRY_TYPE: ENTRY_TYPE_RECEIVER,
                        CONF_GATEWAY_INDEX: 0,
                        CONF_GATEWAY_SERIAL: MOCK_GATEWAY_SERIAL,
                        CONF_RECEIVER_KIND: receiver_kind,
                    },
                }
            ]
        },
    )


def _patch_integration() -> tuple[Any, Any, Any, Any]:
    """Return patches for transceiver and coordinator."""
    mock_transceiver = MagicMock()
    mock_transceiver.is_connected = True
    mock_transceiver.usb_serial_number = "12345"
    mock_transceiver.hw_version = "1.0"
    mock_transceiver.fw_version = "2.0"
    mock_transceiver.device_path = "/dev/ttyACM0"
    mock_transceiver.send_command = AsyncMock(return_value=True)

    mock_coordinator = MagicMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()
    mock_coordinator.async_shutdown = AsyncMock()
    mock_coordinator.async_add_listener = MagicMock(return_value=lambda: None)
    mock_coordinator.transceiver = mock_transceiver
    mock_coordinator.is_offline = False
    mock_coordinator.register_transmitter_entities = MagicMock()
    mock_coordinator.data = {"is_connected": True, "device_path": "/dev/ttyACM0"}

    transceiver_patch = patch(
        "homeassistant.components.easywave.RX11Transceiver",
        return_value=mock_transceiver,
    )
    coordinator_patch = patch(
        "homeassistant.components.easywave.EasywaveCoordinator",
        return_value=mock_coordinator,
    )

    return transceiver_patch, coordinator_patch, mock_transceiver, mock_coordinator


async def test_switch_setup(hass: HomeAssistant) -> None:
    """Test switch entity is created from receiver config entry."""
    gateway = _make_gateway()
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    t_patch, c_patch, _mock_transceiver, _mock_coordinator = _patch_integration()
    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(_get_switch_entity_id(hass))
    assert state is not None
    assert state.state == "off"


async def test_switch_turn_on(hass: HomeAssistant) -> None:
    """Test turning on the switch sends button A command."""
    gateway = _make_gateway()
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    t_patch, c_patch, mock_transceiver, _mock_coordinator = _patch_integration()
    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": _get_switch_entity_id(hass)},
            blocking=True,
        )

    mock_transceiver.send_command.assert_called_once_with(
        bytes.fromhex(MOCK_GATEWAY_SERIAL), 0
    )


async def test_switch_turn_off(hass: HomeAssistant) -> None:
    """Test turning off the switch sends button B command."""
    gateway = _make_gateway()
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    t_patch, c_patch, mock_transceiver, _mock_coordinator = _patch_integration()
    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": _get_switch_entity_id(hass)},
            blocking=True,
        )

    mock_transceiver.send_command.assert_called_once_with(
        bytes.fromhex(MOCK_GATEWAY_SERIAL), 1
    )


async def test_switch_unavailable_when_disconnected(hass: HomeAssistant) -> None:
    """Test switch is unavailable when transceiver is disconnected."""
    gateway = _make_gateway()
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    t_patch, c_patch, mock_transceiver, _mock_coordinator = _patch_integration()
    mock_transceiver.is_connected = False

    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(_get_switch_entity_id(hass))
    assert state is not None
    assert state.state == "unavailable"

"""Tests for the Easywave button platform."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.easywave.const import (
    CONF_ENTRY_TYPE,
    CONF_GATEWAY_INDEX,
    CONF_GATEWAY_SERIAL,
    CONF_RECEIVER_KIND,
    DOMAIN,
    ENTRY_TYPE_RECEIVER,
    RECEIVER_KIND_UNIVERSAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_ENTRY_DATA, MOCK_GATEWAY_SERIAL

from tests.common import MockConfigEntry

MOCK_SUBENTRY_ID = "receiver_subentry_test"


def _make_gateway(receiver_kind: str) -> MockConfigEntry:
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
                    "title": "Test Button",
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


def _get_entity_id_by_unique_id(hass: HomeAssistant, suffix: str) -> str:
    """Look up entity_id via unique_id in the entity registry."""
    unique_id = f"{MOCK_SUBENTRY_ID}_button_{suffix}"
    registry = er.async_get(hass)
    entity_entry = registry.async_get_entity_id("button", DOMAIN, unique_id)
    assert entity_entry is not None, f"No entity for unique_id {unique_id}"
    return entity_entry


async def test_universal_buttons_setup(hass: HomeAssistant) -> None:
    """Test universal mode creates 4 button entities."""
    gateway = _make_gateway(RECEIVER_KIND_UNIVERSAL)
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    t_patch, c_patch, _mock_transceiver, _mock_coordinator = _patch_integration()
    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    for suffix in ("a", "b", "c", "d"):
        entity_id = _get_entity_id_by_unique_id(hass, suffix)
        state = hass.states.get(entity_id)
        assert state is not None, f"Button {suffix} not found"


async def test_universal_button_d_press(hass: HomeAssistant) -> None:
    """Test pressing universal button D sends button D command (code 3)."""
    gateway = _make_gateway(RECEIVER_KIND_UNIVERSAL)
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    t_patch, c_patch, mock_transceiver, _mock_coordinator = _patch_integration()
    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

        entity_id = _get_entity_id_by_unique_id(hass, "d")
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": entity_id},
            blocking=True,
        )

    mock_transceiver.send_command.assert_called_once_with(
        bytes.fromhex(MOCK_GATEWAY_SERIAL), 3
    )

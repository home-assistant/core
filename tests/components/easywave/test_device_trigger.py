"""Tests for the Easywave device triggers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components import automation
from homeassistant.components.device_automation import InvalidDeviceAutomationConfig
from homeassistant.components.easywave.const import (
    CONF_BUTTON_COUNT,
    CONF_ENTRY_TYPE,
    CONF_OPERATING_TYPE,
    CONF_TRANSMITTER_SERIAL,
    DOMAIN,
    ENTRY_TYPE_TRANSMITTER,
    EVENT_EASYWAVE,
)
from homeassistant.components.easywave.device_trigger import (
    ALL_TRIGGER_TYPES,
    async_get_triggers,
    async_validate_trigger_config,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import MOCK_ENTRY_DATA, MOCK_TRANSMITTER_SERIAL

from tests.common import MockConfigEntry, async_mock_service

SUBENTRY_ID = "transmitter_subentry_dt"


def _make_gateway(button_count: int = 4) -> MockConfigEntry:
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
                    "id": SUBENTRY_ID,
                    "title": "Test Transmitter",
                    "unique_id": f"transmitter_{MOCK_TRANSMITTER_SERIAL}",
                    "data": {
                        CONF_ENTRY_TYPE: ENTRY_TYPE_TRANSMITTER,
                        CONF_TRANSMITTER_SERIAL: MOCK_TRANSMITTER_SERIAL,
                        CONF_OPERATING_TYPE: "1",
                        CONF_BUTTON_COUNT: button_count,
                    },
                }
            ]
        },
    )


def _make_motor_gateway() -> MockConfigEntry:
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
                    "id": SUBENTRY_ID,
                    "title": "Test Motor Transmitter",
                    "unique_id": f"transmitter_{MOCK_TRANSMITTER_SERIAL}",
                    "data": {
                        CONF_ENTRY_TYPE: ENTRY_TYPE_TRANSMITTER,
                        CONF_TRANSMITTER_SERIAL: MOCK_TRANSMITTER_SERIAL,
                        CONF_OPERATING_TYPE: "3",
                        CONF_BUTTON_COUNT: 3,
                    },
                }
            ]
        },
    )


def _patch_integration() -> tuple:
    transceiver = MagicMock()
    transceiver.is_connected = True
    transceiver.usb_serial_number = "12345"
    transceiver.hw_version = "1.0"
    transceiver.fw_version = "2.0"
    transceiver.device_path = "/dev/ttyACM0"

    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.async_shutdown = AsyncMock()
    coordinator.async_add_listener = MagicMock(return_value=lambda: None)
    coordinator.transceiver = transceiver
    coordinator.is_offline = False
    coordinator.register_transmitter_entities = MagicMock()
    coordinator.data = {"is_connected": True, "device_path": "/dev/ttyACM0"}

    return (
        patch(
            "homeassistant.components.easywave.RX11Transceiver",
            return_value=transceiver,
        ),
        patch(
            "homeassistant.components.easywave.EasywaveCoordinator",
            return_value=coordinator,
        ),
    )


async def _setup_transmitter(hass: HomeAssistant, button_count: int = 4) -> str:
    """Set up the transmitter and return its HA device id."""
    gateway = _make_gateway(button_count=button_count)
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    t_patch, c_patch = _patch_integration()
    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, SUBENTRY_ID)})
    assert device_entry is not None
    return device_entry.id


async def _setup_motor_transmitter(hass: HomeAssistant) -> str:
    """Set up a type-3 motor transmitter and return its HA device id."""
    gateway = _make_motor_gateway()
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    t_patch, c_patch = _patch_integration()
    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, SUBENTRY_ID)})
    assert device_entry is not None
    return device_entry.id


@pytest.mark.parametrize(
    ("button_count", "expected_press_count"),
    [(1, 1), (2, 2), (3, 3), (4, 4)],
)
async def test_get_triggers(
    hass: HomeAssistant, button_count: int, expected_press_count: int
) -> None:
    """Verify number of pressed triggers matches button_count plus one release."""
    device_id = await _setup_transmitter(hass, button_count=button_count)
    triggers = await async_get_triggers(hass, device_id)
    types = [t[CONF_TYPE] for t in triggers]
    assert len([t for t in types if t.endswith("_pressed")]) == expected_press_count
    assert "button_released" in types
    assert "battery_low" in types
    assert "battery_normal" in types
    # Buttons + release + 2 battery triggers
    assert len(triggers) == expected_press_count + 3


async def test_get_triggers_unknown_device(hass: HomeAssistant) -> None:
    """Return empty list for unknown device id."""
    triggers = await async_get_triggers(hass, "non-existent-device-id")
    assert triggers == []


async def test_validate_trigger_config_invalid_device(hass: HomeAssistant) -> None:
    """Reject config for an unknown device."""
    with pytest.raises(InvalidDeviceAutomationConfig):
        await async_validate_trigger_config(
            hass,
            {
                CONF_PLATFORM: "device",
                CONF_DOMAIN: DOMAIN,
                CONF_DEVICE_ID: "non-existent",
                CONF_TYPE: "button_a_pressed",
            },
        )


async def test_button_pressed_trigger_fires(hass: HomeAssistant) -> None:
    """An automation listening for button_a_pressed should fire on the HA event."""
    device_id = await _setup_transmitter(hass)
    calls = async_mock_service(hass, "test", "automation")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device_id,
                        CONF_TYPE: "button_a_pressed",
                    },
                    "action": {"service": "test.automation"},
                }
            ]
        },
    )
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_EASYWAVE,
        {"device_id": device_id, "type": "button_a_pressed"},
    )
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_button_released_trigger_fires(hass: HomeAssistant) -> None:
    """The universal button_released trigger should fire on a release event."""
    device_id = await _setup_transmitter(hass)
    calls = async_mock_service(hass, "test", "automation")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device_id,
                        CONF_TYPE: "button_released",
                    },
                    "action": {"service": "test.automation"},
                }
            ]
        },
    )
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_EASYWAVE,
        {"device_id": device_id, "type": "button_released"},
    )
    await hass.async_block_till_done()
    assert len(calls) == 1


def test_all_trigger_types_complete() -> None:
    """All expected types are exposed."""
    assert {
        "button_a_pressed",
        "button_b_pressed",
        "button_c_pressed",
        "button_d_pressed",
        "button_released",
        "opened",
        "closed",
        "stopped",
        "battery_low",
        "battery_normal",
        "state_a",
        "state_b",
        "state_c",
        "state_d",
        "state_released",
        "gateway_connected",
        "gateway_disconnected",
    } == ALL_TRIGGER_TYPES


async def test_motor_transmitter_triggers(hass: HomeAssistant) -> None:
    """Type-3 motor transmitters expose opened/closed/stopped triggers plus battery."""
    device_id = await _setup_motor_transmitter(hass)
    triggers = await async_get_triggers(hass, device_id)
    types = {t[CONF_TYPE] for t in triggers}
    assert types == {
        "opened",
        "closed",
        "stopped",
        "battery_low",
        "battery_normal",
    }


async def test_motor_trigger_fires(hass: HomeAssistant) -> None:
    """An automation listening for 'opened' should fire on the HA event."""
    device_id = await _setup_motor_transmitter(hass)
    calls = async_mock_service(hass, "test", "automation")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device_id,
                        CONF_TYPE: "opened",
                    },
                    "action": {"service": "test.automation"},
                }
            ]
        },
    )
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_EASYWAVE,
        {"device_id": device_id, "type": "opened"},
    )
    await hass.async_block_till_done()
    assert len(calls) == 1

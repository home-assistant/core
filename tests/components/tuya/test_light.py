"""Test Tuya light platform."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice

from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.tuya import ManagerCompat
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.LIGHT])
async def test_platform_setup_and_discovery(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_devices: list[CustomerDevice],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test platform setup and discovery."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_devices)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "mock_device_code",
    ["dj_mki13ie507rlry4r"],
)
async def test_turn_on_white(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test turn_on service."""
    entity_id = "light.garage_light"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            "entity_id": entity_id,
            "white": True,
        },
    )
    await hass.async_block_till_done()
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id,
        [
            {"code": "switch_led", "value": True},
            {"code": "work_mode", "value": "white"},
            {"code": "bright_value_v2", "value": 546},
        ],
    )


@pytest.mark.parametrize(
    "mock_device_code",
    ["dj_mki13ie507rlry4r"],
)
async def test_turn_on_brightness(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test turn_on service."""
    entity_id = "light.garage_light"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            "entity_id": entity_id,
            "brightness": 150,
        },
    )
    await hass.async_block_till_done()
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id,
        [
            {"code": "switch_led", "value": True},
            {"code": "bright_value_v2", "value": 592},
        ],
    )


@pytest.mark.parametrize(
    "mock_device_code",
    ["dj_mki13ie507rlry4r"],
)
async def test_turn_on_white_and_brightness_1(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test turn_on service."""
    entity_id = "light.garage_light"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            "entity_id": entity_id,
            "white": True,
            "brightness": 150,
        },
    )
    await hass.async_block_till_done()
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id,
        [
            {"code": "switch_led", "value": True},
            {"code": "work_mode", "value": "white"},
            {"code": "bright_value_v2", "value": 592},
        ],
    )


@pytest.mark.parametrize(
    "mock_device_code",
    ["dj_mki13ie507rlry4r"],
)
async def test_turn_on_white_and_brightness_2(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test turn_on service."""
    entity_id = "light.garage_light"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            "entity_id": entity_id,
            "white": 150,
        },
    )
    await hass.async_block_till_done()
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id,
        [
            {"code": "switch_led", "value": True},
            {"code": "work_mode", "value": "white"},
            {"code": "bright_value_v2", "value": 592},
        ],
    )


@pytest.mark.parametrize(
    "mock_device_code",
    ["dj_mki13ie507rlry4r"],
)
async def test_turn_off(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test turn_off service."""
    entity_id = "light.garage_light"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {
            "entity_id": entity_id,
        },
    )
    await hass.async_block_till_done()
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, [{"code": "switch_led", "value": False}]
    )

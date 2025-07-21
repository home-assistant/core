"""Test Tuya humidifier platform."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice

from homeassistant.components.humidifier import (
    DOMAIN as HUMIDIFIER_DOMAIN,
    SERVICE_SET_HUMIDITY,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.tuya import ManagerCompat
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import DEVICE_MOCKS, initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    "mock_device_code", [k for k, v in DEVICE_MOCKS.items() if Platform.HUMIDIFIER in v]
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.HUMIDIFIER])
async def test_platform_setup_and_discovery(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test platform setup and discovery."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "mock_device_code",
    [k for k, v in DEVICE_MOCKS.items() if Platform.HUMIDIFIER not in v],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.HUMIDIFIER])
async def test_platform_setup_no_discovery(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test platform setup without discovery."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )


@pytest.mark.parametrize(
    "mock_device_code",
    ["cs_arete_two_12l_dehumidifier_air_purifier"],
)
async def test_turn_on(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test turn on service."""
    entity_id = "humidifier.dehumidifier"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": entity_id},
    )
    await hass.async_block_till_done()
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, [{"code": "switch", "value": True}]
    )


@pytest.mark.parametrize(
    "mock_device_code",
    ["cs_arete_two_12l_dehumidifier_air_purifier"],
)
async def test_turn_off(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test turn off service."""
    entity_id = "humidifier.dehumidifier"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {"entity_id": entity_id},
    )
    await hass.async_block_till_done()
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, [{"code": "switch", "value": False}]
    )


@pytest.mark.parametrize(
    "mock_device_code",
    ["cs_arete_two_12l_dehumidifier_air_purifier"],
)
async def test_set_humidity(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test set humidity service."""
    entity_id = "humidifier.dehumidifier"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {
            "entity_id": entity_id,
            "humidity": 50,
        },
    )
    await hass.async_block_till_done()
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, [{"code": "dehumidify_set_value", "value": 50}]
    )

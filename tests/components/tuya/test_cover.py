"""Test Tuya cover platform."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
)
from homeassistant.components.tuya import ManagerCompat
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotSupported
from homeassistant.helpers import entity_registry as er

from . import initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.COVER])
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
    ["cl_zah67ekd"],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.COVER])
async def test_open_service(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test open service."""
    entity_id = "cover.kitchen_blinds_curtain"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {
            "entity_id": entity_id,
        },
    )
    await hass.async_block_till_done()
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id,
        [
            {"code": "control", "value": "open"},
            {"code": "percent_control", "value": 0},
        ],
    )


@pytest.mark.parametrize(
    "mock_device_code",
    ["cl_zah67ekd"],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.COVER])
async def test_close_service(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test close service."""
    entity_id = "cover.kitchen_blinds_curtain"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {
            "entity_id": entity_id,
        },
    )
    await hass.async_block_till_done()
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id,
        [
            {"code": "control", "value": "close"},
            {"code": "percent_control", "value": 100},
        ],
    )


@pytest.mark.parametrize(
    "mock_device_code",
    ["cl_zah67ekd"],
)
async def test_set_position(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test set position service (not available on this device)."""
    entity_id = "cover.kitchen_blinds_curtain"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {
            "entity_id": entity_id,
            "position": 25,
        },
    )
    await hass.async_block_till_done()
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id,
        [
            {"code": "percent_control", "value": 75},
        ],
    )


@pytest.mark.parametrize(
    "mock_device_code",
    ["cl_zah67ekd"],
)
@pytest.mark.parametrize(
    ("percent_control", "percent_state"),
    [
        (100, 52),
        (0, 100),
        (50, 25),
    ],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.COVER])
async def test_percent_state_on_cover(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    percent_control: int,
    percent_state: int,
) -> None:
    """Test percent_state attribute on the cover entity."""
    mock_device.status["percent_control"] = percent_control
    # 100 is closed and 0 is open for Tuya covers
    mock_device.status["percent_state"] = 100 - percent_state

    entity_id = "cover.kitchen_blinds_curtain"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    assert state.attributes["current_position"] == percent_state


@pytest.mark.parametrize(
    "mock_device_code",
    ["cl_zah67ekd"],
)
async def test_set_tilt_position_not_supported(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test set tilt position service (not available on this device)."""
    entity_id = "cover.kitchen_blinds_curtain"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    with pytest.raises(ServiceNotSupported):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_TILT_POSITION,
            {
                "entity_id": entity_id,
                "tilt_position": 50,
            },
            blocking=True,
        )

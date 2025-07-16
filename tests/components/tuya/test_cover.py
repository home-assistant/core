"""Test Tuya cover platform."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice

from homeassistant.components.tuya import ManagerCompat
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import DEVICE_MOCKS, initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    "mock_device_code",
    [k for k, v in DEVICE_MOCKS.items() if Platform.COVER in v],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.COVER])
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
    [k for k, v in DEVICE_MOCKS.items() if Platform.COVER not in v],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.COVER])
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
    ["cl_am43_corded_motor_zigbee_cover"],
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

    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    cover_state = hass.states.get("cover.kitchen_blinds_curtain")
    assert cover_state is not None, "cover.kitchen_blinds_curtain does not exist"
    assert cover_state.attributes["current_position"] == percent_state


@pytest.mark.parametrize(
    ("mock_device_code", "entity_id", "service_name", "expected_commands"),
    [
        (
            "clkg_curtain_switch",
            "cover.tapparelle_studio_curtain",
            "close_cover",
            [
                # Current (bad) behavior - may need to be adjusted see
                # https://github.com/home-assistant/core/issues/136055
                {"code": "control", "value": "close"},
                {"code": "percent_control", "value": 100},
            ],
        ),
        (
            "clkg_curtain_switch",
            "cover.tapparelle_studio_curtain",
            "open_cover",
            [
                # Current (bad) behavior - may need to be adjusted see
                # https://github.com/home-assistant/core/issues/136055
                {"code": "control", "value": "open"},
                {"code": "percent_control", "value": 0},
            ],
        ),
    ],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.COVER])
async def test_service(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    service_name: str,
    entity_id: str,
    expected_commands: list[dict[str, Any]],
) -> None:
    """Test percent_state attribute on the cover entity."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    await hass.services.async_call(
        Platform.COVER,
        service_name,
        {
            "entity_id": entity_id,
        },
    )
    await hass.async_block_till_done()

    mock_manager.send_commands.assert_called_once_with(
        mock_device.id,
        expected_commands,
    )

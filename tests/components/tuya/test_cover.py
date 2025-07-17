"""Test Tuya cover platform."""

from __future__ import annotations

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
    ("mock_device_code", "entity_id"),
    [
        ("clkg_curtain_switch", "cover.tapparelle_studio_curtain"),
    ],
)
@pytest.mark.parametrize(
    (
        "tuya_control",
        "tuya_position",
        "expected_state",
        "expected_ha_position",
        "control_back_mode",
    ),
    [
        # Forward mode: Tuya 100 = closed, 0 = open, HA 100 = open, 0 = closed
        ("open", 100, "closed", 0, "forward"),
        ("close", 0, "open", 100, "forward"),
        ("stop", 50, "open", 50, "forward"),
        # Back mode: Tuya 0 = closed, 100 = open, HA 100 = open, 0 = closed
        ("open", 0, "closed", 0, "back"),
        ("close", 100, "open", 100, "back"),
        ("stop", 50, "open", 50, "back"),
    ],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.COVER])
async def test_curtain_direction_mapping_control_back_mode(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    entity_id: str,
    tuya_control: str,
    tuya_position: int,
    expected_state: str,
    expected_ha_position: int,
    control_back_mode: str,
) -> None:
    """Test direction of control_back_mode."""
    mock_device.status["control"] = tuya_control
    mock_device.status["percent_control"] = tuya_position
    mock_device.status["control_back_mode"] = control_back_mode
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"

    assert state.state == expected_state, (
        f"{entity_id}: {state.state} != {expected_state} (mode={control_back_mode})"
    )
    assert state.attributes.get("current_position") == expected_ha_position

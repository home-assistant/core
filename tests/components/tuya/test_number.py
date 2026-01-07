"""Test Tuya number platform."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockDeviceListener, initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.NUMBER])
async def test_platform_setup_and_discovery(
    hass: HomeAssistant,
    mock_manager: Manager,
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
    ["mal_gyitctrjj1kefxp2"],
)
@pytest.mark.parametrize(
    ("updates", "expected_state", "last_reported"),
    [
        ({"switch_alarm_sound": True}, "15.0", "2024-01-01T00:00:00+00:00"),
        ({"delay_set": 17}, "17.0", "2024-01-01T00:01:00+00:00"),
    ],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.NUMBER])
@pytest.mark.freeze_time("2024-01-01")
async def test_last_reported(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    mock_listener: MockDeviceListener,
    freezer: FrozenDateTimeFactory,
    updates: dict[str, Any],
    expected_state: str,
    last_reported: str,
) -> None:
    """Test skip_update/last_reported."""
    entity_id = "number.multifunction_alarm_arm_delay"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    assert hass.states.get(entity_id).state == "15.0"
    assert (
        hass.states.get(entity_id).last_reported.isoformat()
        == "2024-01-01T00:00:00+00:00"
    )

    freezer.tick(60)
    await mock_listener.async_send_device_update(hass, mock_device, updates)

    assert hass.states.get(entity_id).state == expected_state
    assert hass.states.get(entity_id).last_reported.isoformat() == last_reported


@pytest.mark.parametrize(
    "mock_device_code",
    ["mal_gyitctrjj1kefxp2"],
)
async def test_set_value(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test set value."""
    entity_id = "number.multifunction_alarm_arm_delay"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_VALUE: 18,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, [{"code": "delay_set", "value": 18}]
    )

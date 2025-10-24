"""Test Tuya binary sensor platform."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockDeviceListener, initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.BINARY_SENSOR])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
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
    ["cs_zibqa9dutqyaxym2"],
)
@pytest.mark.parametrize(
    ("fault_value", "tankfull", "defrost", "wet"),
    [
        (0, "off", "off", "off"),
        (0x1, "on", "off", "off"),
        (0x2, "off", "on", "off"),
        (0x80, "off", "off", "on"),
        (0x83, "on", "on", "on"),
    ],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.BINARY_SENSOR])
async def test_bitmap(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    mock_listener: MockDeviceListener,
    fault_value: int,
    tankfull: str,
    defrost: str,
    wet: str,
) -> None:
    """Test BITMAP fault sensor on cs_zibqa9dutqyaxym2."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    assert hass.states.get("binary_sensor.dehumidifier_tank_full").state == "off"
    assert hass.states.get("binary_sensor.dehumidifier_defrost").state == "off"
    assert hass.states.get("binary_sensor.dehumidifier_wet").state == "off"

    await mock_listener.async_send_device_update(
        hass, mock_device, {"fault": fault_value}
    )

    assert hass.states.get("binary_sensor.dehumidifier_tank_full").state == tankfull
    assert hass.states.get("binary_sensor.dehumidifier_defrost").state == defrost
    assert hass.states.get("binary_sensor.dehumidifier_wet").state == wet

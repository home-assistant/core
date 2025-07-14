"""Test Tuya humidifier platform."""

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


@pytest.mark.parametrize("mock_device_code", ["cs_pro_breeze_30l_dehumidifier"])
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.HUMIDIFIER])
async def test_humidifier_missing_dpcodes(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test humidifier setup with real Pro Breeze device missing required DPCodes."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    # No entities should be created for device without required DPCodes
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    # Check that warning was logged for real Pro Breeze device
    assert (
        "Skipping dehumidifier device 'Pro Breeze 30L Compressor Dehumidifier'"
        in caplog.text
    )
    assert "does not support any of the expected control codes" in caplog.text

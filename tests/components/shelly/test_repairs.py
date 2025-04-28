"""Test repairs handling for Shelly."""

from unittest.mock import Mock

from homeassistant.components.shelly.const import (
    BLE_SCANNER_FIRMWARE_UNSUPPORTED_ISSUE_ID,
    CONF_BLE_SCANNER_MODE,
    DOMAIN,
    BLEScannerMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from . import MOCK_MAC, init_integration


async def test_ble_scanner_unsupported_firmware_issue(
    hass: HomeAssistant, mock_rpc_device: Mock, issue_registry: ir.IssueRegistry
) -> None:
    """Test repair issues handling for BLE scanner with unsupported firmware."""
    await init_integration(
        hass, 2, options={CONF_BLE_SCANNER_MODE: BLEScannerMode.ACTIVE}
    )

    await hass.async_block_till_done(wait_background_tasks=True)
    assert issue_registry.async_get_issue(
        DOMAIN, BLE_SCANNER_FIRMWARE_UNSUPPORTED_ISSUE_ID.format(unique=MOCK_MAC)
    )

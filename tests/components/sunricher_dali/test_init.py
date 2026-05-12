"""Test the Sunricher DALI integration initialization."""

from unittest.mock import MagicMock

from PySrDaliGateway.exceptions import DaliGatewayError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sunricher_dali.const import (
    DOMAIN,
    MIN_SUPPORTED_FW_VERSION,
    MIN_SUPPORTED_SW_VERSION,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from tests.common import MockConfigEntry


def _register_stale_firmware_issue(hass: HomeAssistant) -> None:
    """Pre-register an unsupported_firmware issue to simulate one carried over from a prior setup."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        "unsupported_firmware",
        is_fixable=False,
        is_persistent=True,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.ERROR,
        translation_key="unsupported_firmware",
        translation_placeholders={
            "sw_version": "3.50",
            "fw_version": "1.30",
            "min_sw_version": MIN_SUPPORTED_SW_VERSION,
            "min_fw_version": MIN_SUPPORTED_FW_VERSION,
        },
    )


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
) -> None:
    """Test successful setup of config entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_gateway.connect.assert_called_once()


async def test_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that devices are registered correctly."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert devices == snapshot


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
) -> None:
    """Test setup fails when gateway connection fails."""
    mock_config_entry.add_to_hass(hass)
    mock_gateway.connect.side_effect = DaliGatewayError("Connection failed")

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_gateway.connect.assert_called_once()


async def test_setup_entry_discovery_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
) -> None:
    """Test setup fails when device discovery fails."""
    mock_config_entry.add_to_hass(hass)
    mock_gateway.discover_devices.side_effect = DaliGatewayError("Discovery failed")

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_gateway.connect.assert_called_once()
    mock_gateway.discover_devices.assert_called_once()


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
) -> None:
    """Test successful unloading of config entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_remove_stale_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
    mock_devices: list[MagicMock],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test stale devices are removed when device list decreases."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    devices_before = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    initial_count = len(devices_before)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_gateway.discover_devices.return_value = mock_devices[:2]

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    devices_after = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(devices_after) < initial_count

    gateway_device = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_gateway.gw_sn)}
    )
    assert gateway_device is not None
    assert mock_config_entry.entry_id in gateway_device.config_entries


@pytest.mark.parametrize(
    ("sw_version", "fw_version"),
    [
        ("3.50", "1.45"),  # software too old
        ("3.59", "1.30"),  # firmware too old
        ("3.50", "1.30"),  # both too old
    ],
)
async def test_firmware_check_creates_issue_when_too_old(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
    issue_registry: ir.IssueRegistry,
    sw_version: str,
    fw_version: str,
) -> None:
    """Repair issue is raised when either reported version is below the minimum."""
    mock_gateway.software_version = sw_version
    mock_gateway.firmware_version = fw_version
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    issue = issue_registry.async_get_issue(DOMAIN, "unsupported_firmware")
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.ERROR
    assert issue.is_fixable is False
    assert issue.translation_placeholders == {
        "sw_version": sw_version,
        "fw_version": fw_version,
        "min_sw_version": MIN_SUPPORTED_SW_VERSION,
        "min_fw_version": MIN_SUPPORTED_FW_VERSION,
    }


@pytest.mark.parametrize(
    ("sw_version", "fw_version"),
    [
        (MIN_SUPPORTED_SW_VERSION, MIN_SUPPORTED_FW_VERSION),  # exactly at threshold
        ("3.99", "1.99"),  # above threshold
    ],
)
async def test_firmware_check_deletes_issue_when_versions_ok(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
    issue_registry: ir.IssueRegistry,
    sw_version: str,
    fw_version: str,
) -> None:
    """Existing repair issue is cleared once the gateway reports supported versions."""
    _register_stale_firmware_issue(hass)
    assert issue_registry.async_get_issue(DOMAIN, "unsupported_firmware") is not None

    mock_gateway.software_version = sw_version
    mock_gateway.firmware_version = fw_version
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, "unsupported_firmware") is None


@pytest.mark.parametrize(
    ("sw_version", "fw_version"),
    [
        ("", "1.45"),  # software version not yet reported
        ("3.59", ""),  # firmware version not yet reported
        ("not-a-version", "1.45"),  # software version unparsable
        ("3.59", "??"),  # firmware version unparsable
    ],
)
async def test_firmware_check_skips_when_version_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
    issue_registry: ir.IssueRegistry,
    sw_version: str,
    fw_version: str,
) -> None:
    """Empty or unparsable versions skip the check without touching existing issues."""
    _register_stale_firmware_issue(hass)

    mock_gateway.software_version = sw_version
    mock_gateway.firmware_version = fw_version
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Pre-existing issue is preserved (not deleted) and no new issue is created.
    assert issue_registry.async_get_issue(DOMAIN, "unsupported_firmware") is not None


async def test_firmware_check_no_op_when_no_issue_and_versions_ok(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Deleting a non-existent issue is safe and produces no spurious issue."""
    mock_gateway.software_version = "3.99"
    mock_gateway.firmware_version = "1.99"
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, "unsupported_firmware") is None

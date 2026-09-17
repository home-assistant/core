"""Test the sma init file."""

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

from pysma import (
    SmaAuthenticationException,
    SmaConnectionException,
    SmaReadException,
    SmaSunSpecException,
    SmaTimeoutException,
)
import pytest

from homeassistant.components.sma.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from . import MOCK_DEVICE, MOCK_USER_INPUT, setup_integration

from tests.common import MockConfigEntry


async def test_migrate_entry_minor_version_1_2(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sma_client: AsyncGenerator,
) -> None:
    """Test migrating a 1.1 config entry to 1.2."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_DEVICE.name,
        unique_id=MOCK_DEVICE.serial,
        data=MOCK_USER_INPUT,
        source=SOURCE_IMPORT,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.version == 1
    assert entry.minor_version == 2
    assert isinstance(MOCK_DEVICE.serial, str)
    assert entry.unique_id == MOCK_DEVICE.serial


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (SmaConnectionException, ConfigEntryState.SETUP_RETRY),
        (SmaAuthenticationException, ConfigEntryState.SETUP_ERROR),
        (SmaReadException, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_exceptions(
    hass: HomeAssistant,
    mock_sma_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test the _async_setup."""
    mock_sma_client.device_info.side_effect = exception
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is expected_state


@pytest.mark.parametrize(
    ("failing_step", "exception"),
    [
        pytest.param("connect", SmaConnectionException, id="connection_exception"),
        pytest.param("connect", SmaTimeoutException, id="timeout_exception"),
        pytest.param("discover", SmaSunSpecException, id="sunspec_exception"),
    ],
)
async def test_modbus_discovery_failure_creates_issue(
    hass: HomeAssistant,
    mock_sma_client: MagicMock,
    mock_sma_modbus: MagicMock,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    failing_step: str,
    exception: type[Exception],
) -> None:
    """Test a Modbus connection or discovery failure creates a repair issue."""
    getattr(mock_sma_modbus, failing_step).side_effect = exception
    await setup_integration(hass, mock_config_entry)

    issue = issue_registry.async_get_issue(
        DOMAIN, f"modbus_not_enabled_{mock_config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_key == "modbus_not_enabled"


async def test_modbus_discovery_success_creates_no_issue(
    hass: HomeAssistant,
    mock_sma_client: MagicMock,
    mock_sma_modbus: MagicMock,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a successful Modbus discovery does not create a repair issue."""
    await setup_integration(hass, mock_config_entry)

    issue = issue_registry.async_get_issue(
        DOMAIN, f"modbus_not_enabled_{mock_config_entry.entry_id}"
    )
    assert issue is None


async def test_modbus_issue_removed_on_unload(
    hass: HomeAssistant,
    mock_sma_client: MagicMock,
    mock_sma_modbus: MagicMock,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the repair issue is removed when the config entry is unloaded."""
    mock_sma_modbus.connect.side_effect = SmaConnectionException
    await setup_integration(hass, mock_config_entry)

    issue_id = f"modbus_not_enabled_{mock_config_entry.entry_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None

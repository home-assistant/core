"""Test the SMA repairs."""

from unittest.mock import MagicMock

from pysma import SmaConnectionException
import pytest

from homeassistant.components.repairs import ConfirmRepairFlow
from homeassistant.components.sma.const import CONF_MODBUS, DOMAIN
from homeassistant.components.sma.repairs import async_create_fix_flow
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import MOCK_DEVICE, MOCK_MODBUS_OPTIONS, MOCK_USER_INPUT, setup_integration

from tests.common import MockConfigEntry
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator

ISSUE_ID = "modbus_unreachable_sma_entry_123"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry with Modbus enabled."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_DEVICE.name,
        unique_id=str(MOCK_DEVICE.serial),
        data=MOCK_USER_INPUT,
        options=MOCK_MODBUS_OPTIONS,
        minor_version=2,
        entry_id="sma_entry_123",
    )


@pytest.fixture(autouse=True)
async def _setup_unreachable_modbus(
    hass: HomeAssistant,
    mock_sma_client: MagicMock,
    mock_sma_modbus: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Set up the entry with Modbus unreachable, which creates the issue."""
    assert await async_setup_component(hass, "repairs", {})
    mock_sma_modbus.connect.side_effect = SmaConnectionException
    await setup_integration(hass, mock_config_entry)


@pytest.mark.parametrize(
    "options",
    [
        pytest.param(MOCK_MODBUS_OPTIONS, id="fixed"),
        pytest.param({**MOCK_MODBUS_OPTIONS, CONF_MODBUS: False}, id="disabled"),
    ],
)
async def test_repair_flow(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_sma_modbus: MagicMock,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    options: dict[str, int | bool],
) -> None:
    """Test fixing the issue saves the options and reloads the entry."""
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID)
    mock_sma_modbus.connect.side_effect = None
    client = await hass_client()

    result = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await process_repair_fix_flow(client, result["flow_id"], options)
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == options
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not issue_registry.async_get_issue(DOMAIN, ISSUE_ID)


async def test_repair_flow_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_sma_modbus: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the repair flow keeps the form open while Modbus is unreachable."""
    client = await hass_client()

    result = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)
    result = await process_repair_fix_flow(
        client, result["flow_id"], MOCK_MODBUS_OPTIONS
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "modbus_cannot_connect"}

    mock_sma_modbus.connect.side_effect = None
    result = await process_repair_fix_flow(
        client, result["flow_id"], MOCK_MODBUS_OPTIONS
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == MOCK_MODBUS_OPTIONS


async def test_repair_flow_without_entry(hass: HomeAssistant) -> None:
    """Test a confirm flow is used when the config entry is gone."""
    flow = await async_create_fix_flow(hass, ISSUE_ID, {"entry_id": "unknown"})

    assert isinstance(flow, ConfirmRepairFlow)

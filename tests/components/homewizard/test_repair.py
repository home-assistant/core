"""Test the homewizard config flow."""

from unittest.mock import MagicMock, patch

from homewizard_energy.errors import DisabledError, RequestError
import pytest

from homeassistant.components.homewizard.const import (
    DOMAIN,
    battery_mode_cloud_issue_id,
)
from homeassistant.components.homewizard.repairs import async_create_fix_flow
from homeassistant.components.repairs import ConfirmRepairFlow
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.repairs import (
    async_process_repairs_platforms,
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from tests.typing import ClientSessionGenerator


async def test_repair_acquires_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
    mock_homewizardenergy_v2: MagicMock,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repair flow is able to obtain and use token."""

    assert await async_setup_component(hass, "repairs", {})
    await async_process_repairs_platforms(hass)
    client = await hass_client()

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, unique_id="HWE-BAT_5c2fafabcdef"
    )
    await hass.async_block_till_done()

    with patch("homeassistant.components.homewizard.has_v2_api", return_value=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Get active repair flow
    issue_id = f"migrate_to_v2_api_{mock_config_entry.entry_id}"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None

    assert issue.data.get("entry_id") == mock_config_entry.entry_id

    mock_homewizardenergy_v2.get_token.side_effect = DisabledError

    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = result["flow_id"]
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await process_repair_fix_flow(client, flow_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "authorize"

    # Simulate user not pressing the button
    result = await process_repair_fix_flow(client, flow_id, json={})

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "authorize"
    assert result["errors"] == {"base": "authorization_failed"}

    # Simulate user pressing the button and getting a new token
    mock_homewizardenergy_v2.get_token.side_effect = None
    mock_homewizardenergy_v2.get_token.return_value = "cool_token"
    result = await process_repair_fix_flow(client, flow_id, json={})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert mock_config_entry.data[CONF_TOKEN] == "cool_token"
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_repair_created_for_cloud_disabled_predictive_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repair issue is created for incompatible cloud and battery mode."""
    mock_homewizardenergy.combined.return_value.system.cloud_enabled = False
    mock_homewizardenergy.combined.return_value.batteries.mode = "predictive"

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    issue_id = battery_mode_cloud_issue_id(mock_config_entry.entry_id)
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.data.get("entry_id") == mock_config_entry.entry_id


async def test_repair_auto_resolves_when_cloud_is_re_enabled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repair issue is auto-resolved when compatibility is restored."""
    mock_homewizardenergy.combined.return_value.system.cloud_enabled = False
    mock_homewizardenergy.combined.return_value.batteries.mode = "predictive"

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    issue_id = battery_mode_cloud_issue_id(mock_config_entry.entry_id)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    mock_homewizardenergy.combined.return_value.system.cloud_enabled = True
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_repair_confirm_enables_cloud_connection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test confirming repair enables cloud connection and resolves issue."""
    assert await async_setup_component(hass, "repairs", {})
    await async_process_repairs_platforms(hass)
    client = await hass_client()

    combined_data = mock_homewizardenergy.combined.return_value
    combined_data.system.cloud_enabled = False
    combined_data.batteries.mode = "predictive"

    def _set_cloud_enabled(*, cloud_enabled: bool) -> None:
        combined_data.system.cloud_enabled = cloud_enabled

    mock_homewizardenergy.system.side_effect = _set_cloud_enabled

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    issue_id = battery_mode_cloud_issue_id(mock_config_entry.entry_id)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    result = await start_repair_fix_flow(client, DOMAIN, issue_id)
    flow_id = result["flow_id"]
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await process_repair_fix_flow(client, flow_id, json={})
    assert result["type"] == FlowResultType.CREATE_ENTRY

    mock_homewizardenergy.system.assert_called_with(cloud_enabled=True)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (RequestError, "network_error"),
    ],
)
async def test_repair_confirm_enable_cloud_connection_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    exception: type[Exception],
    expected_error: str,
) -> None:
    """Test confirming repair returns recoverable errors if cloud enable fails."""
    assert await async_setup_component(hass, "repairs", {})
    await async_process_repairs_platforms(hass)
    client = await hass_client()

    combined_data = mock_homewizardenergy.combined.return_value
    combined_data.system.cloud_enabled = False
    combined_data.batteries.mode = "predictive"
    mock_homewizardenergy.system.side_effect = exception

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    issue_id = battery_mode_cloud_issue_id(mock_config_entry.entry_id)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    result = await start_repair_fix_flow(client, DOMAIN, issue_id)
    flow_id = result["flow_id"]
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await process_repair_fix_flow(client, flow_id, json={})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": expected_error}
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None


async def test_repair_unknown_issue_id_raises(hass: HomeAssistant) -> None:
    """Test unknown repair issue id raises ValueError."""
    with pytest.raises(ValueError, match="unknown repair unknown_issue"):
        await async_create_fix_flow(hass, "unknown_issue", {"entry_id": "entry-id"})


@pytest.mark.parametrize(
    "data",
    [
        None,
        {"entry_id": None},
        {"entry_id": 123},
    ],
)
async def test_repair_invalid_entry_id_returns_confirm_flow(
    hass: HomeAssistant,
    data: dict[str, str | int | float | None] | None,
) -> None:
    """Test invalid repair flow data falls back to confirm flow."""
    flow = await async_create_fix_flow(hass, "any_issue", data)
    assert isinstance(flow, ConfirmRepairFlow)

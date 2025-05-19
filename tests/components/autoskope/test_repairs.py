"""Tests for the Autoskope repairs."""

import logging
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.autoskope.const import DOMAIN
from homeassistant.components.autoskope.models import CannotConnect, InvalidAuth
from homeassistant.components.autoskope.repairs import (
    AuthFailureRepairsFlow,
    CannotConnectRepairFlow,
    async_create_fix_flow,
    create_auth_issue,
    create_connection_issue,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry


@pytest.fixture
async def mock_issue_registry(hass: HomeAssistant) -> ir.IssueRegistry:
    """Mock issue registry."""
    return ir.async_get(hass)


@pytest.fixture
def mock_api() -> AsyncMock:
    """Fixture for a mocked AutoskopeApi instance."""
    return AsyncMock(spec=True)


@pytest.fixture
def mock_autoskope_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> MockConfigEntry:
    """Set up the Autoskope integration with mocks."""
    mock_config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {
        "api": mock_api,
        "coordinator": AsyncMock(api=mock_api),
    }
    return mock_config_entry


async def test_create_connection_issue(
    hass: HomeAssistant,
    mock_issue_registry: ir.IssueRegistry,
) -> None:
    """Test create_connection_issue registers an issue."""
    entry_id = "test_entry_id_conn"
    with patch(
        "homeassistant.helpers.issue_registry.async_create_issue"
    ) as mock_create_issue:
        create_connection_issue(hass, entry_id)

        mock_create_issue.assert_called_once_with(
            hass,
            DOMAIN,
            f"cannot_connect_{entry_id}",
            is_fixable=True,
            translation_key="cannot_connect",
            severity=ir.IssueSeverity.WARNING,
            translation_placeholders={"entry_id": entry_id},
            data={"entry_id": entry_id},
        )


async def test_cannot_connect_repair_flow_init(
    hass: HomeAssistant, mock_issue_registry: ir.IssueRegistry
) -> None:
    """Test CannotConnectRepairFlow init step."""
    entry_id = "test_entry_init"
    issue_id = f"cannot_connect_{entry_id}"
    issue_data = {"entry_id": entry_id}
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        translation_key="cannot_connect",
        severity=ir.IssueSeverity.WARNING,
        translation_placeholders={"entry_id": entry_id},
        data=issue_data,
    )
    await hass.async_block_till_done()

    flow = await async_create_fix_flow(hass, issue_id, issue_data)
    assert isinstance(flow, CannotConnectRepairFlow)

    result = await flow.async_step_confirm(user_input=None)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"


async def test_cannot_connect_repair_flow_confirm_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_issue_registry: ir.IssueRegistry,
) -> None:
    """Test CannotConnectRepairFlow confirm step (successful case)."""
    entry = mock_config_entry
    entry.add_to_hass(hass)
    issue_id = f"cannot_connect_{entry.entry_id}"
    issue_data = {"entry_id": entry.entry_id}
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        translation_key="cannot_connect",
        severity=ir.IssueSeverity.WARNING,
        translation_placeholders={"entry_id": entry.entry_id},
        data=issue_data,
    )
    await hass.async_block_till_done()

    flow = await async_create_fix_flow(hass, issue_id, issue_data)
    assert isinstance(flow, CannotConnectRepairFlow)

    mock_api_success = AsyncMock()
    mock_api_success.authenticate = AsyncMock(return_value=True)

    with (
        patch(
            "homeassistant.components.autoskope.repairs.AutoskopeApi",
            return_value=mock_api_success,
        ) as mock_api_init,
        patch("homeassistant.helpers.issue_registry.async_delete_issue") as mock_delete,
    ):
        result_success = await flow.async_step_confirm(user_input={})
        await hass.async_block_till_done()

    assert result_success["type"] == FlowResultType.ABORT
    assert result_success["reason"] == "repaired"
    mock_api_init.assert_called_once()
    mock_delete.assert_called_once_with(hass, DOMAIN, issue_id)


async def test_async_create_fix_flow(hass: HomeAssistant) -> None:
    """Test async_create_fix_flow function."""
    flow = await async_create_fix_flow(
        hass, "cannot_connect_test_entry", {"entry_id": "test_entry"}
    )
    assert isinstance(flow, CannotConnectRepairFlow)

    flow = await async_create_fix_flow(
        hass, "invalid_auth_test_entry", {"entry_id": "test_entry"}
    )
    assert isinstance(flow, AuthFailureRepairsFlow)

    with pytest.raises(ValueError, match="Unknown or unsupported repair issue ID"):
        await async_create_fix_flow(hass, "unknown_issue_test_entry", {})


async def test_auth_failure_repairs_flow(hass: HomeAssistant) -> None:
    """Test AuthFailureRepairsFlow."""
    entry_id = "test_entry_auth"
    issue_id = f"invalid_auth_{entry_id}"
    issue_data = {"entry_id": entry_id}
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        translation_key="invalid_auth",
        severity=ir.IssueSeverity.ERROR,
        translation_placeholders={"entry_id": entry_id},
        data=issue_data,
    )
    await hass.async_block_till_done()

    flow = await async_create_fix_flow(hass, issue_id, issue_data)
    assert isinstance(flow, AuthFailureRepairsFlow)

    result_init = await flow.async_step_confirm(user_input=None)
    assert result_init["type"] == FlowResultType.FORM
    assert result_init["step_id"] == "confirm"

    with patch(
        "homeassistant.config_entries.ConfigEntriesFlowManager.async_init"
    ) as mock_reauth_init:
        result_confirm = await flow.async_step_confirm({"confirm": True})
        await hass.async_block_till_done()

        mock_reauth_init.assert_called_once_with(
            DOMAIN,
            context={"source": "reauth", "entry_id": entry_id},
            data=None,
        )
        assert result_confirm["type"] == FlowResultType.ABORT
        assert result_confirm["reason"] == "reauth_triggered"


async def test_repair_cannot_connect_confirm_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_issue_registry: ir.IssueRegistry,
) -> None:
    """Test the cannot connect repair flow confirm step with API error."""
    mock_config_entry.add_to_hass(hass)
    issue_id = f"cannot_connect_{mock_config_entry.entry_id}"
    issue_data = {"entry_id": mock_config_entry.entry_id}
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        translation_key="cannot_connect",
        severity=ir.IssueSeverity.ERROR,
        translation_placeholders={"entry_id": mock_config_entry.entry_id},
        data=issue_data,
    )
    await hass.async_block_till_done()

    flow = await async_create_fix_flow(hass, issue_id, issue_data)
    assert isinstance(flow, CannotConnectRepairFlow)

    mock_api_fail = AsyncMock()
    mock_api_fail.authenticate = AsyncMock(
        side_effect=CannotConnect("Still cannot connect")
    )

    with (
        patch(
            "homeassistant.components.autoskope.repairs.AutoskopeApi",
            return_value=mock_api_fail,
        ) as mock_api_init,
        patch("homeassistant.helpers.issue_registry.async_delete_issue") as mock_delete,
    ):
        result_confirm = await flow.async_step_confirm(user_input={})
        await hass.async_block_till_done()

    assert result_confirm["type"] == FlowResultType.FORM
    assert result_confirm["step_id"] == "confirm"
    assert result_confirm["errors"] == {"base": "cannot_connect"}
    mock_api_init.assert_called_once()
    mock_delete.assert_not_called()


async def test_create_auth_issue(
    hass: HomeAssistant,
    mock_issue_registry: ir.IssueRegistry,
) -> None:
    """Test create_auth_issue registers an issue."""
    entry_id = "test_entry_id_auth"
    with patch(
        "homeassistant.helpers.issue_registry.async_create_issue"
    ) as mock_create_issue:
        create_auth_issue(hass, entry_id)

        mock_create_issue.assert_called_once_with(
            hass,
            DOMAIN,
            f"invalid_auth_{entry_id}",
            is_fixable=True,
            translation_key="invalid_auth",
            severity=ir.IssueSeverity.ERROR,
            translation_placeholders={"entry_id": entry_id},
            data={"entry_id": entry_id},
        )


async def test_cannot_connect_repair_flow_confirm_missing_entry_id(
    hass: HomeAssistant, mock_issue_registry: ir.IssueRegistry
) -> None:
    """Test CannotConnectRepairFlow confirm step with missing entry_id in data."""
    issue_id = "cannot_connect_missing_entry"
    issue_data = {"some_other_key": "value"}
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        translation_key="cannot_connect",
        severity=ir.IssueSeverity.WARNING,
        data=issue_data,
    )
    await hass.async_block_till_done()

    flow = await async_create_fix_flow(hass, issue_id, issue_data)
    assert isinstance(flow, CannotConnectRepairFlow)

    # Call confirm step
    result = await flow.async_step_confirm(user_input={})
    await hass.async_block_till_done()

    # Should abort with unknown_error because entry_id is missing
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown_error"


async def test_cannot_connect_repair_flow_confirm_entry_not_found(
    hass: HomeAssistant, mock_issue_registry: ir.IssueRegistry
) -> None:
    """Test CannotConnectRepairFlow confirm step when config entry is not found."""
    entry_id = "non_existent_entry"
    issue_id = f"cannot_connect_{entry_id}"
    issue_data = {"entry_id": entry_id}
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        translation_key="cannot_connect",
        severity=ir.IssueSeverity.WARNING,
        data=issue_data,
    )
    await hass.async_block_till_done()

    flow = await async_create_fix_flow(hass, issue_id, issue_data)
    assert isinstance(flow, CannotConnectRepairFlow)

    # Ensure async_get_entry returns None
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_get_entry", return_value=None
    ):
        result = await flow.async_step_confirm(user_input={})
        await hass.async_block_till_done()

    # Should abort with unknown_error because entry is not found
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown_error"


async def test_cannot_connect_repair_flow_confirm_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_issue_registry: ir.IssueRegistry,
) -> None:
    """Test CannotConnectRepairFlow confirm step with InvalidAuth during check."""
    mock_config_entry.add_to_hass(hass)
    issue_id = f"cannot_connect_{mock_config_entry.entry_id}"
    issue_data = {"entry_id": mock_config_entry.entry_id}
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        translation_key="cannot_connect",
        severity=ir.IssueSeverity.WARNING,
        data=issue_data,
    )
    await hass.async_block_till_done()

    flow = await async_create_fix_flow(hass, issue_id, issue_data)
    assert isinstance(flow, CannotConnectRepairFlow)

    # Mock API to raise InvalidAuth
    mock_api_fail = AsyncMock()
    mock_api_fail.authenticate = AsyncMock(side_effect=InvalidAuth("Auth failed"))

    with patch(
        "homeassistant.components.autoskope.repairs.AutoskopeApi",
        return_value=mock_api_fail,
    ):
        result = await flow.async_step_confirm(user_input={})
        await hass.async_block_till_done()

    # Should show form again with invalid_auth error
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_cannot_connect_repair_flow_confirm_generic_exception(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_issue_registry: ir.IssueRegistry,
) -> None:
    """Test CannotConnectRepairFlow confirm step with generic Exception during check."""
    mock_config_entry.add_to_hass(hass)
    issue_id = f"cannot_connect_{mock_config_entry.entry_id}"
    issue_data = {"entry_id": mock_config_entry.entry_id}
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        translation_key="cannot_connect",
        severity=ir.IssueSeverity.WARNING,
        data=issue_data,
    )
    await hass.async_block_till_done()

    flow = await async_create_fix_flow(hass, issue_id, issue_data)
    assert isinstance(flow, CannotConnectRepairFlow)

    # Mock API to raise generic Exception
    mock_api_fail = AsyncMock()
    mock_api_fail.authenticate = AsyncMock(side_effect=Exception("Something broke"))

    with patch(
        "homeassistant.components.autoskope.repairs.AutoskopeApi",
        return_value=mock_api_fail,
    ):
        result = await flow.async_step_confirm(user_input={})
        await hass.async_block_till_done()

    # Should show form again with unknown error
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": "unknown"}


async def test_auth_failure_repair_flow_confirm_missing_entry_id(
    hass: HomeAssistant, mock_issue_registry: ir.IssueRegistry
) -> None:
    """Test AuthFailureRepairsFlow confirm step with missing entry_id in data."""
    issue_id = "invalid_auth_missing_entry"
    # Create issue data without entry_id
    issue_data = {"some_other_key": "value"}
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        translation_key="invalid_auth",
        severity=ir.IssueSeverity.ERROR,
        data=issue_data,
    )
    await hass.async_block_till_done()

    flow = await async_create_fix_flow(hass, issue_id, issue_data)
    assert isinstance(flow, AuthFailureRepairsFlow)

    # Call confirm step
    result = await flow.async_step_confirm(user_input={"confirm": True})
    await hass.async_block_till_done()

    # Should abort with unknown_error because entry_id is missing
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown_error"


async def test_cannot_connect_repair_flow_step_init(
    hass: HomeAssistant, mock_issue_registry: ir.IssueRegistry
) -> None:
    """Test CannotConnectRepairFlow init step directly."""
    entry_id = "test_entry_init_step"
    issue_id = f"cannot_connect_{entry_id}"
    issue_data = {"entry_id": entry_id}
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        data=issue_data,
        severity=ir.IssueSeverity.WARNING,
        translation_key="cannot_connect",
    )
    await hass.async_block_till_done()

    flow = await async_create_fix_flow(hass, issue_id, issue_data)
    assert isinstance(flow, CannotConnectRepairFlow)

    # Call init step
    result = await flow.async_step_init(user_input=None)

    # Init should delegate to confirm and show the form
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"


async def test_auth_failure_repair_flow_step_init(
    hass: HomeAssistant, mock_issue_registry: ir.IssueRegistry
) -> None:
    """Test AuthFailureRepairsFlow init step directly."""
    entry_id = "test_auth_init_step"
    issue_id = f"invalid_auth_{entry_id}"
    issue_data = {"entry_id": entry_id}
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        data=issue_data,
        severity=ir.IssueSeverity.ERROR,
        translation_key="invalid_auth",
    )
    await hass.async_block_till_done()

    flow = await async_create_fix_flow(hass, issue_id, issue_data)
    assert isinstance(flow, AuthFailureRepairsFlow)

    # Call init step
    result = await flow.async_step_init(user_input=None)

    # Init should delegate to confirm and show the form
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"


async def test_cannot_connect_repair_flow_non_string_entry_id(
    hass: HomeAssistant,
    mock_issue_registry: ir.IssueRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test CannotConnectRepairFlow confirm step with non-string entry_id."""
    issue_id = "cannot_connect_non_string"
    # Create issue data with non-string entry_id
    issue_data = {"entry_id": 12345}
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        data=issue_data,
        severity=ir.IssueSeverity.WARNING,
        translation_key="cannot_connect",
    )
    await hass.async_block_till_done()

    flow = await async_create_fix_flow(hass, issue_id, issue_data)
    assert isinstance(flow, CannotConnectRepairFlow)

    # Call confirm step (user_input=None to just show form)
    caplog.set_level(logging.WARNING)
    result = await flow.async_step_confirm(user_input=None)
    await hass.async_block_till_done()

    # Should show form, but log a warning
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert "Unexpected type for entry_id" in caplog.text
    assert str(int) in caplog.text


async def test_auth_failure_repair_flow_non_string_entry_id(
    hass: HomeAssistant,
    mock_issue_registry: ir.IssueRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test AuthFailureRepairsFlow confirm step with non-string entry_id."""
    issue_id = "invalid_auth_non_string"
    # Create issue data with non-string entry_id
    issue_data = {"entry_id": 67890}
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        data=issue_data,
        severity=ir.IssueSeverity.ERROR,
        translation_key="invalid_auth",
    )
    await hass.async_block_till_done()

    flow = await async_create_fix_flow(hass, issue_id, issue_data)
    assert isinstance(flow, AuthFailureRepairsFlow)

    # Call confirm step (user_input=None to just show form)
    caplog.set_level(logging.WARNING)
    result = await flow.async_step_confirm(user_input=None)
    await hass.async_block_till_done()

    # Should show form, but log a warning
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert "Unexpected type for entry_id" in caplog.text
    assert str(int) in caplog.text

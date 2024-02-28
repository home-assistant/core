"""Tests for the Tuya config flow."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.tuya.const import CONF_APP_TYPE, CONF_USER_CODE, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.usefixtures("mock_tuya_login_control")
async def test_user_flow(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the full happy path user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "scan"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result3.get("type") == FlowResultType.CREATE_ENTRY
    assert result3 == snapshot


async def test_user_flow_failed_qr_code(
    hass: HomeAssistant,
    mock_tuya_login_control: MagicMock,
) -> None:
    """Test an error occurring while retrieving the QR code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"

    # Something went wrong getting the QR code (like an invalid user code)
    mock_tuya_login_control.qr_code.return_value["success"] = False

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("errors") == {"base": "login_error"}

    # This time it worked out
    mock_tuya_login_control.qr_code.return_value["success"] = True

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )
    assert result3.get("step_id") == "scan"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result3.get("type") == FlowResultType.CREATE_ENTRY


async def test_user_flow_failed_scan(
    hass: HomeAssistant,
    mock_tuya_login_control: MagicMock,
) -> None:
    """Test an error occurring while verifying login."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "scan"

    # Access has been denied, or the code hasn't been scanned yet
    good_values = mock_tuya_login_control.login_result.return_value
    mock_tuya_login_control.login_result.return_value = (
        False,
        {"msg": "oops", "code": 42},
    )

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result3.get("type") == FlowResultType.FORM
    assert result3.get("errors") == {"base": "login_error"}

    # This time it worked out
    mock_tuya_login_control.login_result.return_value = good_values

    result4 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result4.get("type") == FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_tuya_login_control")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the reauthentication configuration flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_config_entry.unique_id,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "scan"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result2.get("type") == FlowResultType.ABORT
    assert result2.get("reason") == "reauth_successful"

    assert mock_config_entry == snapshot


@pytest.mark.usefixtures("mock_tuya_login_control")
async def test_reauth_flow_migration(
    hass: HomeAssistant,
    mock_old_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the reauthentication configuration flow.

    This flow tests the migration from an old config entry.
    """
    mock_old_config_entry.add_to_hass(hass)

    # Ensure old data is there, new data is missing
    assert CONF_APP_TYPE in mock_old_config_entry.data
    assert CONF_USER_CODE not in mock_old_config_entry.data

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_old_config_entry.unique_id,
            "entry_id": mock_old_config_entry.entry_id,
        },
        data=mock_old_config_entry.data,
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "reauth_user_code"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "scan"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result3.get("type") == FlowResultType.ABORT
    assert result3.get("reason") == "reauth_successful"

    # Ensure the old data is gone, new data is present
    assert CONF_APP_TYPE not in mock_old_config_entry.data
    assert CONF_USER_CODE in mock_old_config_entry.data

    assert mock_old_config_entry == snapshot


async def test_reauth_flow_failed_qr_code(
    hass: HomeAssistant,
    mock_tuya_login_control: MagicMock,
    mock_old_config_entry: MockConfigEntry,
) -> None:
    """Test an error occurring while retrieving the QR code."""
    mock_old_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_old_config_entry.unique_id,
            "entry_id": mock_old_config_entry.entry_id,
        },
        data=mock_old_config_entry.data,
    )

    # Something went wrong getting the QR code (like an invalid user code)
    mock_tuya_login_control.qr_code.return_value["success"] = False

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("errors") == {"base": "login_error"}

    # This time it worked out
    mock_tuya_login_control.qr_code.return_value["success"] = True

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )
    assert result3.get("step_id") == "scan"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result3.get("type") == FlowResultType.ABORT
    assert result3.get("reason") == "reauth_successful"

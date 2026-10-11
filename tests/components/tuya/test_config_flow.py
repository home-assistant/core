"""Tests for the Tuya config flow."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.tuya.const import (
    CONF_REFRESH_QR_CODE,
    CONF_USER_CODE,
    DOMAIN,
    TUYA_CLIENT_ID,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import selector

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

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("step_id") == "scan"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result3.get("type") is FlowResultType.CREATE_ENTRY
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

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    # Something went wrong getting the QR code (like an invalid user code)
    mock_tuya_login_control.qr_code.return_value["success"] = False

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )

    assert result2.get("type") is FlowResultType.FORM
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

    assert result3.get("type") is FlowResultType.CREATE_ENTRY


async def test_user_flow_failed_scan(
    hass: HomeAssistant,
    mock_tuya_login_control: MagicMock,
) -> None:
    """Test an error occurring while verifying login."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )

    assert result2.get("type") is FlowResultType.FORM
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

    assert result3.get("type") is FlowResultType.FORM
    assert result3.get("errors") == {"base": "login_error"}

    # This time it worked out
    mock_tuya_login_control.login_result.return_value = good_values

    result4 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result4.get("type") is FlowResultType.CREATE_ENTRY


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_tuya_login_control: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the reauthentication configuration flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"

    # A reauth flow can sit untouched for days, so the QR code must not be
    # requested before the user is ready to scan it.
    mock_tuya_login_control.qr_code.assert_not_called()

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("step_id") == "scan"
    mock_tuya_login_control.qr_code.assert_called_once()

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result3.get("type") is FlowResultType.ABORT
    assert result3.get("reason") == "reauth_successful"

    assert mock_config_entry == snapshot


async def test_reauth_flow_refresh_qr_code(
    hass: HomeAssistant,
    mock_tuya_login_control: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Refresh a stale QR without checking login, then complete reauthentication."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    mock_tuya_login_control.qr_code.return_value = {
        "success": False,
        "msg": "oops",
        "code": 42,
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_REFRESH_QR_CODE: True}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "scan"
    assert result["errors"] == {"base": "login_error"}
    qr_selector = next(
        field
        for field in result["data_schema"].schema.values()
        if isinstance(field, selector.QrCodeSelector)
    )
    assert qr_selector.config["data"] == "tuyaSmart--qrLogin?token=mocked_qr_code"
    mock_tuya_login_control.login_result.assert_not_called()

    mock_tuya_login_control.qr_code.return_value = {
        "success": True,
        "result": {"qrcode": "refreshed_qr_code"},
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_REFRESH_QR_CODE: True}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "scan"
    assert not result["errors"]
    qr_selector = next(
        field
        for field in result["data_schema"].schema.values()
        if isinstance(field, selector.QrCodeSelector)
    )
    assert qr_selector.config["data"] == "tuyaSmart--qrLogin?token=refreshed_qr_code"
    assert mock_tuya_login_control.qr_code.call_count == 3
    mock_tuya_login_control.login_result.assert_not_called()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    mock_tuya_login_control.login_result.assert_called_once_with(
        "refreshed_qr_code", TUYA_CLIENT_ID, "test_user_code"
    )


async def test_reauth_flow_without_user_code(
    hass: HomeAssistant,
    mock_tuya_login_control: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauthentication of an entry that predates the stored user code."""
    mock_config_entry.add_to_hass(hass)
    data = dict(mock_config_entry.data)
    del data[CONF_USER_CODE]
    hass.config_entries.async_update_entry(mock_config_entry, data=data)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_user_code"
    mock_tuya_login_control.qr_code.assert_not_called()

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("step_id") == "scan"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result3.get("type") is FlowResultType.ABORT
    assert result3.get("reason") == "reauth_successful"


async def test_reauth_flow_failed_qr_code(
    hass: HomeAssistant,
    mock_tuya_login_control: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an error occurring while retrieving the QR code."""
    mock_config_entry.add_to_hass(hass)

    # Something went wrong getting the QR code (like an invalid user code)
    mock_tuya_login_control.qr_code.return_value["success"] = False

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("step_id") == "reauth_user_code"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USER_CODE: "12345"},
    )

    assert result3.get("type") is FlowResultType.FORM
    assert result3.get("errors") == {"base": "login_error"}

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

    assert result3.get("type") is FlowResultType.ABORT
    assert result3.get("reason") == "reauth_successful"

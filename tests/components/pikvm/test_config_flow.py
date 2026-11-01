"""Tests for the PiKVM config flow."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pikvm_aio import (
    PiKVMAuthenticationError,
    PiKVMConnectionError,
    PiKVMDeviceError,
    PiKVMDeviceInfo,
    PiKVMTimeoutError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.pikvm.const import CONF_TOTP, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import SERIAL

USER_INPUT = {
    CONF_HOST: "192.168.1.50",
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "secret",
    CONF_VERIFY_SSL: False,
}
TOTP_SECRET = "JBSWY3DPEHPK3PXP"


@pytest.mark.usefixtures("mock_pikvm_client")
@pytest.mark.parametrize(
    "user_input",
    [
        pytest.param(USER_INPUT, id="defaults"),
        pytest.param({**USER_INPUT, CONF_TOTP: TOTP_SECRET}, id="with_totp"),
        pytest.param(
            {**USER_INPUT, CONF_TOTP: "23456723456723456723456723456723"},
            id="with_numeric_base32_totp",
        ),
        pytest.param({**USER_INPUT, CONF_VERIFY_SSL: True}, id="verify_ssl"),
    ],
)
async def test_user_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, user_input: dict[str, Any]
) -> None:
    """Test the full happy path user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "pikvm"
    assert result["data"] == user_input
    assert result["result"].unique_id == SERIAL
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        pytest.param(PiKVMAuthenticationError, "invalid_auth", id="invalid_auth"),
        pytest.param(PiKVMConnectionError, "cannot_connect", id="connection_error"),
        pytest.param(PiKVMTimeoutError, "cannot_connect", id="timeout"),
        pytest.param(PiKVMDeviceError, "cannot_connect", id="device_error"),
        pytest.param(Exception, "unknown", id="unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_pikvm_client: MagicMock,
    side_effect: type[Exception],
    expected_error: str,
) -> None:
    """Test the user flow shows errors and recovers."""
    mock_pikvm_client.get_info.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_pikvm_client.get_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("user_input", "client_side_effect", "expected_errors"),
    [
        pytest.param(
            {**USER_INPUT, CONF_TOTP: "123 456"},
            None,
            {CONF_TOTP: "invalid_totp"},
            id="one_time_code",
        ),
        pytest.param(
            {**USER_INPUT, CONF_TOTP: "not-base32!"},
            PiKVMAuthenticationError,
            {CONF_TOTP: "invalid_totp"},
            id="invalid_totp_secret",
        ),
        pytest.param(
            {**USER_INPUT, CONF_HOST: "pikvm.local:99999"},
            ValueError,
            {CONF_HOST: "invalid_host"},
            id="invalid_host",
        ),
    ],
)
async def test_user_flow_invalid_input(
    hass: HomeAssistant,
    mock_pikvm_client_class: MagicMock,
    user_input: dict[str, Any],
    client_side_effect: type[Exception] | None,
    expected_errors: dict[str, str],
) -> None:
    """Test invalid input is reported on the field and the flow recovers."""
    mock_pikvm_client_class.side_effect = client_side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == expected_errors

    mock_pikvm_client_class.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={**USER_INPUT, CONF_TOTP: TOTP_SECRET}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_pikvm_client", "mock_setup_entry")
async def test_user_flow_already_configured_host(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the flow aborts when the host is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_pikvm_client", "mock_setup_entry")
async def test_user_flow_already_configured_updates_host(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test adding a known device at a new address updates the stored host."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={**USER_INPUT, CONF_HOST: "pikvm.local"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "pikvm.local"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_missing_serial(
    hass: HomeAssistant, mock_pikvm_client: MagicMock
) -> None:
    """Test the flow aborts when the device reports no serial number."""
    mock_pikvm_client.get_info.return_value = PiKVMDeviceInfo.from_dict({})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_serial"

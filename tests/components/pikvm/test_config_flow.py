"""Tests for the PiKVM config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from pikvm_aio import PiKVMAuthenticationError, PiKVMConnectionError, PiKVMDeviceInfo
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.pikvm.const import CONF_TOTP, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import SERIAL

USER_INPUT = {
    CONF_HOST: "192.168.1.50",
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "secret",
}
TOTP_SECRET = "JBSWY3DPEHPK3PXP"


@pytest.mark.usefixtures("mock_pikvm_client")
@pytest.mark.parametrize(
    "user_input",
    [
        pytest.param(USER_INPUT, id="without_totp"),
        pytest.param({**USER_INPUT, CONF_TOTP: TOTP_SECRET}, id="with_totp"),
    ],
)
async def test_user_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, user_input: dict[str, str]
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
        pytest.param(PiKVMConnectionError, "cannot_connect", id="cannot_connect"),
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


@pytest.mark.usefixtures("mock_pikvm_client", "mock_setup_entry")
async def test_user_flow_one_time_code(hass: HomeAssistant) -> None:
    """Test a one-time code is rejected in favor of the TOTP secret."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={**USER_INPUT, CONF_TOTP: "123 456"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_TOTP: "invalid_totp"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={**USER_INPUT, CONF_TOTP: TOTP_SECRET}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_pikvm_client", "mock_setup_entry")
async def test_user_flow_invalid_totp_secret(hass: HomeAssistant) -> None:
    """Test a TOTP secret the library rejects is reported on the field."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(
        "homeassistant.components.pikvm.coordinator.PiKVMClient",
        side_effect=PiKVMAuthenticationError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={**USER_INPUT, CONF_TOTP: "not-base32!"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_TOTP: "invalid_totp"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={**USER_INPUT, CONF_TOTP: TOTP_SECRET}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_pikvm_client", "mock_setup_entry")
@pytest.mark.parametrize(
    "user_input",
    [
        pytest.param(USER_INPUT, id="same_host"),
        pytest.param({**USER_INPUT, CONF_HOST: "pikvm.local"}, id="same_serial"),
    ],
)
async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    user_input: dict[str, str],
) -> None:
    """Test the flow aborts when the device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


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

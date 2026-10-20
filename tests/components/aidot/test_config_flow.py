"""Test the aidot config flow."""

from unittest.mock import AsyncMock, MagicMock

from aidot.exceptions import AidotUserOrPassIncorrect
from aiohttp import ClientError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.aidot.const import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_COUNTRY_CODE, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import TEST_COUNTRY, TEST_EMAIL, TEST_LOGIN_RESP, TEST_PASSWORD

DHCP_SERVICE_INFO = DhcpServiceInfo(
    hostname="aidot",
    ip="192.168.1.100",
    macaddress="001122334455",
)


async def test_config_flow_cloud_login_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test a successful config flow using cloud login."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY_CODE: TEST_COUNTRY,
            CONF_USERNAME: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{TEST_EMAIL} {TEST_COUNTRY}"
    assert result["data"] == TEST_LOGIN_RESP
    assert result["result"].unique_id == TEST_LOGIN_RESP["id"]


async def test_dhcp_discovery(hass: HomeAssistant) -> None:
    """Test DHCP discovery shows the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_SERVICE_INFO,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_dhcp_discovery_aborts_if_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test DHCP discovery aborts when the integration is configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_SERVICE_INFO,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_discovery_aborts_if_already_in_progress(
    hass: HomeAssistant,
) -> None:
    """Test a duplicate DHCP discovery flow aborts."""
    first_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_SERVICE_INFO,
    )
    assert first_result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_SERVICE_INFO,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (AidotUserOrPassIncorrect, "invalid_auth"),
        (TimeoutError, "cannot_connect"),
        (ClientError, "cannot_connect"),
    ],
)
async def test_config_flow_errors(
    hass: HomeAssistant,
    patch_aidot_client: MagicMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test a failed config flow using cloud connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    patch_aidot_client.async_post_login.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY_CODE: TEST_COUNTRY,
            CONF_USERNAME: TEST_EMAIL,
            CONF_PASSWORD: "ErrorPassword",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    patch_aidot_client.async_post_login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY_CODE: TEST_COUNTRY,
            CONF_USERNAME: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == TEST_LOGIN_RESP


async def test_form_abort_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort if already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY_CODE: TEST_COUNTRY,
            CONF_USERNAME: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    patch_aidot_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test a successful reauthentication flow."""
    mock_config_entry.add_to_hass(hass)
    new_login_info = {**TEST_LOGIN_RESP, "accessToken": "new_token"}
    patch_aidot_client.async_post_login.return_value = new_login_info

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new_password"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == new_login_info
    patch_aidot_client.update_password.assert_called_once_with("new_password")


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(AidotUserOrPassIncorrect, "invalid_auth", id="invalid_auth"),
        pytest.param(TimeoutError, "cannot_connect", id="timeout"),
        pytest.param(ClientError, "cannot_connect", id="client_error"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    patch_aidot_client: MagicMock,
    mock_setup_entry: AsyncMock,
    exception: type[Exception],
    error: str,
) -> None:
    """Test reauthentication errors and recovery."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    patch_aidot_client.async_post_login.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "ErrorPassword"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    patch_aidot_client.async_post_login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: TEST_PASSWORD}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_flow_unique_id_mismatch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    patch_aidot_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauthentication aborts when logging in to a different account."""
    mock_config_entry.add_to_hass(hass)
    patch_aidot_client.async_post_login.return_value = {
        **TEST_LOGIN_RESP,
        "id": "other_account_id",
    }
    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: TEST_PASSWORD}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data == TEST_LOGIN_RESP

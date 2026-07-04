"""Test for vesync config flow."""

from unittest.mock import PropertyMock, patch

from pyvesync.utils.errors import VeSyncLoginError

from homeassistant.components.vesync import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from tests.common import MockConfigEntry


async def test_abort_duplicate_unique_id(hass: HomeAssistant, config_entry) -> None:
    """Test if we abort because component is already setup under that Account ID."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with (
        patch("pyvesync.vesync.VeSync.login"),
        patch(
            "pyvesync.vesync.VeSync.account_id", new_callable=PropertyMock
        ) as mock_account_id,
    ):
        mock_account_id.return_value = "TESTACCOUNTID"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "user@user.com", CONF_PASSWORD: "pass"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_login_error(hass: HomeAssistant) -> None:
    """Test if we return error for invalid username and password."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "pyvesync.vesync.VeSync.login",
        side_effect=VeSyncLoginError("Mock login failed"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_config_flow_user_input(hass: HomeAssistant) -> None:
    """Test config flow with user input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM

    with patch("pyvesync.vesync.VeSync.login"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USERNAME] == "user"
    assert result["data"][CONF_PASSWORD] == "pass"
    assert result["result"].unique_id == "TESTACCOUNTID"


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test a successful reauth flow."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="account_id",
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reauth_flow(hass)

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    with (
        patch("pyvesync.vesync.VeSync") as mock_vesync,
        patch(
            "pyvesync.auth.VeSyncAuth._account_id", new_callable=PropertyMock
        ) as mock_account_id,
    ):
        instance = mock_vesync.return_value
        instance.login.return_value = None
        mock_account_id.return_value = "account_id"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "new-username", CONF_PASSWORD: "new-password"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_entry.data == {
        CONF_USERNAME: "new-username",
        CONF_PASSWORD: "new-password",
    }


async def test_reauth_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Test an authorization error reauth flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="account_id",
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM

    with patch(
        "pyvesync.vesync.VeSync.login",
        side_effect=VeSyncLoginError("Mock login failed"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "new-username", CONF_PASSWORD: "new-password"},
        )

    assert result["type"] is FlowResultType.FORM
    with (
        patch("pyvesync.vesync.VeSync") as mock_vesync,
        patch(
            "pyvesync.auth.VeSyncAuth._account_id", new_callable=PropertyMock
        ) as mock_account_id,
    ):
        instance = mock_vesync.return_value
        instance.login.return_value = None
        mock_account_id.return_value = "account_id"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "new-username", CONF_PASSWORD: "new-password"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_dhcp_discovery(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test DHCP discovery flow."""

    service_info = DhcpServiceInfo(
        hostname="Levoit-Purifier",
        ip="1.2.3.4",
        macaddress="aabbccddeeff",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=service_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # Configure the flow to create the config entry
    with patch("pyvesync.vesync.VeSync.login"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "TESTACCOUNTID"


async def test_dhcp_discovery_duplicate(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test DHCP discovery flow with already setup integration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            hostname="Levoit-Purifier",
            ip="1.2.3.4",
            macaddress="aabbccddeeff",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

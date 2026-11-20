"""Tests for the Moulinex config flow."""

from unittest.mock import ANY, AsyncMock

from aiomoulinex import (
    LoginError,
    LoginFailure,
    MoulinexAuthenticationError,
    MoulinexConnectionError,
    MoulinexError,
    Profile,
    Region,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.moulinex.const import CONF_TOKENS, DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_REGION
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .conftest import EMAIL, USER_ID, build_tokens

PASSWORD = "test-password"
DHCP_DISCOVERY = DhcpServiceInfo(
    ip="192.168.1.20", hostname="seb_product_1a2b", macaddress="aabbccdd1a2b"
)
USER_INPUT = {
    CONF_REGION: Region.MOULINEX_FR,
    CONF_EMAIL: EMAIL,
    CONF_PASSWORD: PASSWORD,
}

ERRORS = [
    *(
        pytest.param("mock_login", LoginError(reason), reason.value, id=reason.value)
        for reason in LoginFailure
    ),
    pytest.param(
        "mock_login",
        MoulinexConnectionError("timeout"),
        "cannot_connect",
        id="login_cannot_connect",
    ),
    pytest.param(
        "mock_login", MoulinexError("unexpected"), "unknown", id="login_unknown"
    ),
    pytest.param(
        "mock_fetch_profile",
        MoulinexAuthenticationError("refused"),
        "invalid_auth",
        id="profile_refused",
    ),
    pytest.param(
        "mock_fetch_profile",
        MoulinexConnectionError("timeout"),
        "cannot_connect",
        id="profile_cannot_connect",
    ),
]


@pytest.mark.usefixtures("mock_fetch_profile")
async def test_user_flow(
    hass: HomeAssistant, mock_login: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """The user logs in and the account is set up."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == EMAIL
    assert result["data"] == {
        CONF_REGION: Region.MOULINEX_FR,
        CONF_EMAIL: EMAIL,
        CONF_TOKENS: build_tokens().to_dict(),
    }
    assert result["result"].unique_id == USER_ID
    mock_login.assert_awaited_once_with(ANY, EMAIL, PASSWORD, Region.MOULINEX_FR)
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(("failing", "exception", "error"), ERRORS)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_login: AsyncMock,
    mock_fetch_profile: AsyncMock,
    failing: str,
    exception: Exception,
    error: str,
) -> None:
    """Each error is shown on the form, and the user can try again."""
    mock = {"mock_login": mock_login, "mock_fetch_profile": mock_fetch_profile}[failing]
    mock.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_login", "mock_fetch_profile")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """An account can only be set up once."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_login", "mock_fetch_profile")
async def test_dhcp_discovery(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """An appliance found on the network leads to the login form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_DISCOVERY
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == EMAIL
    assert result["result"].unique_id == USER_ID
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_discovery_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """An appliance found on the network is ignored once an account is set up."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_DISCOVERY
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_login")
async def test_user_flow_no_appliances(
    hass: HomeAssistant, mock_fetch_profile: AsyncMock
) -> None:
    """An account without a compatible appliance is not set up."""
    mock_fetch_profile.return_value = Profile()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_appliances"

"""Tests for Overkiz (by Somfy) config flow."""
from __future__ import annotations

from ipaddress import ip_address
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientError
from pyoverkiz.exceptions import (
    BadCredentialsException,
    MaintenanceException,
    TooManyAttemptsBannedException,
    TooManyRequestsException,
    UnknownUserException,
)
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import dhcp
from homeassistant.components.overkiz.const import DOMAIN
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

TEST_EMAIL = "test@testdomain.com"
TEST_EMAIL2 = "test@testdomain.nl"
TEST_PASSWORD = "test-password"
TEST_PASSWORD2 = "test-password2"
TEST_HUB = "somfy_europe"
TEST_HUB2 = "hi_kumo_europe"
TEST_HUB_COZYTOUCH = "atlantic_cozytouch"
TEST_GATEWAY_ID = "1234-5678-9123"
TEST_GATEWAY_ID2 = "4321-5678-9123"

MOCK_GATEWAY_RESPONSE = [Mock(id=TEST_GATEWAY_ID)]
MOCK_GATEWAY2_RESPONSE = [Mock(id=TEST_GATEWAY_ID2)]

FAKE_ZERO_CONF_INFO = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.0.51"),
    ip_addresses=[ip_address("192.168.0.51")],
    port=443,
    hostname=f"gateway-{TEST_GATEWAY_ID}.local.",
    type="_kizbox._tcp.local.",
    name=f"gateway-{TEST_GATEWAY_ID}._kizbox._tcp.local.",
    properties={
        "api_version": "1",
        "gateway_pin": TEST_GATEWAY_ID,
        "fw_version": "2021.5.4-29",
    },
)


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch("pyoverkiz.client.OverkizClient.login", return_value=True), patch(
        "pyoverkiz.client.OverkizClient.get_gateways", return_value=None
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD, "hub": TEST_HUB},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == TEST_EMAIL
    assert result2["data"] == {
        "username": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "hub": TEST_HUB,
    }

    await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (BadCredentialsException, "invalid_auth"),
        (TooManyRequestsException, "too_many_requests"),
        (TimeoutError, "cannot_connect"),
        (ClientError, "cannot_connect"),
        (MaintenanceException, "server_in_maintenance"),
        (TooManyAttemptsBannedException, "too_many_attempts"),
        (UnknownUserException, "unsupported_hardware"),
        (Exception, "unknown"),
    ],
)
async def test_form_invalid_auth(
    hass: HomeAssistant, side_effect: Exception, error: str
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("pyoverkiz.client.OverkizClient.login", side_effect=side_effect):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD, "hub": TEST_HUB},
        )

    assert result["step_id"] == config_entries.SOURCE_USER
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": error}


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (BadCredentialsException, "unsupported_hardware"),
    ],
)
async def test_form_invalid_cozytouch_auth(
    hass: HomeAssistant, side_effect: Exception, error: str
) -> None:
    """Test we handle invalid auth from CozyTouch."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("pyoverkiz.client.OverkizClient.login", side_effect=side_effect):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD,
                "hub": TEST_HUB_COZYTOUCH,
            },
        )

    assert result["step_id"] == config_entries.SOURCE_USER
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": error}


async def test_abort_on_duplicate_entry(hass: HomeAssistant) -> None:
    """Test config flow aborts Config Flow on duplicate entries."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD, "hub": TEST_HUB},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("pyoverkiz.client.OverkizClient.login", return_value=True), patch(
        "pyoverkiz.client.OverkizClient.get_gateways",
        return_value=MOCK_GATEWAY_RESPONSE,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_allow_multiple_unique_entries(hass: HomeAssistant) -> None:
    """Test config flow allows Config Flow unique entries."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID2,
        data={"username": "test2@testdomain.com", "password": TEST_PASSWORD},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("pyoverkiz.client.OverkizClient.login", return_value=True), patch(
        "pyoverkiz.client.OverkizClient.get_gateways",
        return_value=MOCK_GATEWAY_RESPONSE,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD, "hub": TEST_HUB},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == TEST_EMAIL
    assert result2["data"] == {
        "username": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "hub": TEST_HUB,
    }


async def test_dhcp_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test that DHCP discovery for new bridge works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=dhcp.DhcpServiceInfo(
            hostname="gateway-1234-5678-9123",
            ip="192.168.1.4",
            macaddress="F8811A000000",
        ),
        context={"source": config_entries.SOURCE_DHCP},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    with patch("pyoverkiz.client.OverkizClient.login", return_value=True), patch(
        "pyoverkiz.client.OverkizClient.get_gateways", return_value=None
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD, "hub": TEST_HUB},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == TEST_EMAIL
    assert result2["data"] == {
        "username": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "hub": TEST_HUB,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_flow_already_configured(hass: HomeAssistant) -> None:
    """Test that DHCP doesn't setup already configured gateways."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD, "hub": TEST_HUB},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=dhcp.DhcpServiceInfo(
            hostname="gateway-1234-5678-9123",
            ip="192.168.1.4",
            macaddress="F8811A000000",
        ),
        context={"source": config_entries.SOURCE_DHCP},
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test that zeroconf discovery for new bridge works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=FAKE_ZERO_CONF_INFO,
        context={"source": config_entries.SOURCE_ZEROCONF},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    with patch("pyoverkiz.client.OverkizClient.login", return_value=True), patch(
        "pyoverkiz.client.OverkizClient.get_gateways", return_value=None
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD, "hub": TEST_HUB},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == TEST_EMAIL
    assert result2["data"] == {
        "username": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "hub": TEST_HUB,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_flow_already_configured(hass: HomeAssistant) -> None:
    """Test that zeroconf doesn't setup already configured gateways."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD, "hub": TEST_HUB},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=FAKE_ZERO_CONF_INFO,
        context={"source": config_entries.SOURCE_ZEROCONF},
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_success(hass: HomeAssistant) -> None:
    """Test reauthentication flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD, "hub": TEST_HUB2},
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": mock_entry.unique_id,
            "entry_id": mock_entry.entry_id,
        },
        data=mock_entry.data,
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch("pyoverkiz.client.OverkizClient.login", return_value=True), patch(
        "pyoverkiz.client.OverkizClient.get_gateways",
        return_value=MOCK_GATEWAY_RESPONSE,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD2,
                "hub": TEST_HUB2,
            },
        )

        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert mock_entry.data["username"] == TEST_EMAIL
        assert mock_entry.data["password"] == TEST_PASSWORD2


async def test_reauth_wrong_account(hass: HomeAssistant) -> None:
    """Test reauthentication flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD, "hub": TEST_HUB2},
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": mock_entry.unique_id,
            "entry_id": mock_entry.entry_id,
        },
        data=mock_entry.data,
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch("pyoverkiz.client.OverkizClient.login", return_value=True), patch(
        "pyoverkiz.client.OverkizClient.get_gateways",
        return_value=MOCK_GATEWAY2_RESPONSE,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD2,
                "hub": TEST_HUB2,
            },
        )

        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "reauth_wrong_account"

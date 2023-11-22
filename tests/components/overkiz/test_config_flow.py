"""Tests for Overkiz config flow."""
from __future__ import annotations

from ipaddress import ip_address
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientConnectorCertificateError, ClientError
from pyoverkiz.exceptions import (
    BadCredentialsException,
    MaintenanceException,
    NotSuchTokenException,
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
TEST_SERVER = "somfy_europe"
TEST_SERVER2 = "hi_kumo_europe"
TEST_SERVER_COZYTOUCH = "atlantic_cozytouch"
TEST_GATEWAY_ID = "1234-5678-9123"
TEST_GATEWAY_ID2 = "4321-5678-9123"
TEST_GATEWAY_ID3 = "SOMFY_PROTECT-v0NT53occUBPyuJRzx59kalW1hFfzimN"

TEST_HOST = "gateway-1234-5678-9123.local:8443"
TEST_HOST2 = "192.168.11.104:8443"

MOCK_GATEWAY_RESPONSE = [Mock(id=TEST_GATEWAY_ID)]
MOCK_GATEWAY2_RESPONSE = [Mock(id=TEST_GATEWAY_ID3), Mock(id=TEST_GATEWAY_ID2)]

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

FAKE_ZERO_CONF_INFO_LOCAL = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.0.51"),
    ip_addresses=[ip_address("192.168.0.51")],
    port=8443,
    hostname=f"gateway-{TEST_GATEWAY_ID}.local.",
    type="_kizboxdev._tcp.local.",
    name=f"gateway-{TEST_GATEWAY_ID}._kizboxdev._tcp.local.",
    properties={
        "api_version": "1",
        "gateway_pin": TEST_GATEWAY_ID,
        "fw_version": "2021.5.4-29",
    },
)


async def test_form_cloud(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER},
    )

    assert result2["type"] == "form"
    assert result2["step_id"] == "local_or_cloud"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "cloud"},
    )

    assert result3["type"] == "form"
    assert result3["step_id"] == "cloud"

    with patch("pyoverkiz.client.OverkizClient.login", return_value=True), patch(
        "pyoverkiz.client.OverkizClient.get_gateways",
        return_value=MOCK_GATEWAY_RESPONSE,
    ):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_only_cloud_supported(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER2},
    )

    assert result2["type"] == "form"
    assert result2["step_id"] == "cloud"

    with patch("pyoverkiz.client.OverkizClient.login", return_value=True), patch(
        "pyoverkiz.client.OverkizClient.get_gateways",
        return_value=MOCK_GATEWAY_RESPONSE,
    ):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_local_happy_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER},
    )

    assert result2["type"] == "form"
    assert result2["step_id"] == "local_or_cloud"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "local"},
    )

    assert result3["type"] == "form"
    assert result3["step_id"] == "local"

    with patch.multiple(
        "pyoverkiz.client.OverkizClient",
        login=AsyncMock(return_value=True),
        get_gateways=AsyncMock(return_value=MOCK_GATEWAY_RESPONSE),
        get_setup_option=AsyncMock(return_value=True),
        generate_local_token=AsyncMock(return_value="1234123412341234"),
        activate_local_token=AsyncMock(return_value=True),
    ):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD,
                "host": "gateway-1234-5678-1234.local:8443",
            },
        )

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
async def test_form_invalid_auth_cloud(
    hass: HomeAssistant, side_effect: Exception, error: str
) -> None:
    """Test we handle invalid auth (cloud)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER},
    )

    assert result2["type"] == "form"
    assert result2["step_id"] == "local_or_cloud"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "cloud"},
    )

    assert result3["type"] == "form"
    assert result3["step_id"] == "cloud"

    with patch("pyoverkiz.client.OverkizClient.login", side_effect=side_effect):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    await hass.async_block_till_done()

    assert result4["type"] == data_entry_flow.FlowResultType.FORM
    assert result4["errors"] == {"base": error}


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (BadCredentialsException, "invalid_auth"),
        (TooManyRequestsException, "too_many_requests"),
        (
            ClientConnectorCertificateError(Mock(host=TEST_HOST), Exception),
            "certificate_verify_failed",
        ),
        (TimeoutError, "cannot_connect"),
        (ClientError, "cannot_connect"),
        (MaintenanceException, "server_in_maintenance"),
        (TooManyAttemptsBannedException, "too_many_attempts"),
        (UnknownUserException, "unsupported_hardware"),
        (NotSuchTokenException, "no_such_token"),
        (Exception, "unknown"),
    ],
)
async def test_form_invalid_auth_local(
    hass: HomeAssistant, side_effect: Exception, error: str
) -> None:
    """Test we handle invalid auth (local)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER},
    )

    assert result2["type"] == "form"
    assert result2["step_id"] == "local_or_cloud"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "local"},
    )

    assert result3["type"] == "form"
    assert result3["step_id"] == "local"

    with patch("pyoverkiz.client.OverkizClient.login", side_effect=side_effect):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": TEST_HOST,
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD,
                "verify_ssl": True,
            },
        )

    await hass.async_block_till_done()

    assert result4["type"] == data_entry_flow.FlowResultType.FORM
    assert result4["errors"] == {"base": error}


async def test_form_local_developer_mode_disabled(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER},
    )

    assert result2["type"] == "form"
    assert result2["step_id"] == "local_or_cloud"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "local"},
    )

    assert result3["type"] == "form"
    assert result3["step_id"] == "local"

    with patch.multiple(
        "pyoverkiz.client.OverkizClient",
        login=AsyncMock(return_value=True),
        get_gateways=AsyncMock(return_value=MOCK_GATEWAY_RESPONSE),
        get_setup_option=AsyncMock(return_value=None),
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD,
                "host": "gateway-1234-5678-1234.local:8443",
                "verify_ssl": True,
            },
        )

    assert result4["type"] == data_entry_flow.FlowResultType.FORM
    assert result4["errors"] == {"base": "developer_mode_disabled"}


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (BadCredentialsException, "unsupported_hardware"),
    ],
)
async def test_form_invalid_cozytouch_auth(
    hass: HomeAssistant, side_effect: Exception, error: str
) -> None:
    """Test we handle invalid auth (cloud)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER_COZYTOUCH},
    )

    assert result2["type"] == "form"
    assert result2["step_id"] == "cloud"

    with patch("pyoverkiz.client.OverkizClient.login", side_effect=side_effect):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    await hass.async_block_till_done()

    assert result3["type"] == data_entry_flow.FlowResultType.FORM
    assert result3["errors"] == {"base": error}
    assert result3["step_id"] == "cloud"


async def test_cloud_abort_on_duplicate_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form."""

    MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD, "hub": TEST_SERVER},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER},
    )

    assert result2["type"] == "form"
    assert result2["step_id"] == "local_or_cloud"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "cloud"},
    )

    assert result3["type"] == "form"
    assert result3["step_id"] == "cloud"

    with patch("pyoverkiz.client.OverkizClient.login", return_value=True), patch(
        "pyoverkiz.client.OverkizClient.get_gateways",
        return_value=MOCK_GATEWAY_RESPONSE,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    assert result4["type"] == data_entry_flow.FlowResultType.ABORT
    assert result4["reason"] == "already_configured"


async def test_local_abort_on_duplicate_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form."""

    MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        data={
            "host": TEST_HOST,
            "username": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "hub": TEST_SERVER,
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER},
    )

    assert result2["type"] == "form"
    assert result2["step_id"] == "local_or_cloud"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "local"},
    )

    assert result3["type"] == "form"
    assert result3["step_id"] == "local"

    with patch.multiple(
        "pyoverkiz.client.OverkizClient",
        login=AsyncMock(return_value=True),
        get_gateways=AsyncMock(return_value=MOCK_GATEWAY_RESPONSE),
        get_setup_option=AsyncMock(return_value=True),
        generate_local_token=AsyncMock(return_value="1234123412341234"),
        activate_local_token=AsyncMock(return_value=True),
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": TEST_HOST,
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD,
                "verify_ssl": True,
            },
        )

    assert result4["type"] == data_entry_flow.FlowResultType.ABORT
    assert result4["reason"] == "already_configured"


async def test_cloud_allow_multiple_unique_entries(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form."""

    MockConfigEntry(
        version=1,
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID2,
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD, "hub": TEST_SERVER},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER},
    )

    assert result2["type"] == "form"
    assert result2["step_id"] == "local_or_cloud"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "cloud"},
    )

    assert result3["type"] == "form"
    assert result3["step_id"] == "cloud"

    with patch("pyoverkiz.client.OverkizClient.login", return_value=True), patch(
        "pyoverkiz.client.OverkizClient.get_gateways",
        return_value=MOCK_GATEWAY_RESPONSE,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    assert result4["type"] == "create_entry"
    assert result4["title"] == TEST_EMAIL
    assert result4["data"] == {
        "api_type": "cloud",
        "username": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "hub": TEST_SERVER,
    }


async def test_cloud_reauth_success(hass: HomeAssistant) -> None:
    """Test reauthentication flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        version=2,
        data={
            "username": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "hub": TEST_SERVER2,
            "api_type": "cloud",
        },
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
    assert result["step_id"] == "cloud"

    with patch("pyoverkiz.client.OverkizClient.login", return_value=True), patch(
        "pyoverkiz.client.OverkizClient.get_gateways",
        return_value=MOCK_GATEWAY_RESPONSE,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD2,
            },
        )

        assert result2["type"] == data_entry_flow.FlowResultType.ABORT
        assert result2["reason"] == "reauth_successful"
        assert mock_entry.data["username"] == TEST_EMAIL
        assert mock_entry.data["password"] == TEST_PASSWORD2


async def test_cloud_reauth_wrong_account(hass: HomeAssistant) -> None:
    """Test reauthentication flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        version=2,
        data={
            "username": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "hub": TEST_SERVER2,
            "api_type": "cloud",
        },
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
    assert result["step_id"] == "cloud"

    with patch("pyoverkiz.client.OverkizClient.login", return_value=True), patch(
        "pyoverkiz.client.OverkizClient.get_gateways",
        return_value=MOCK_GATEWAY2_RESPONSE,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD2,
            },
        )

        assert result2["type"] == data_entry_flow.FlowResultType.ABORT
        assert result2["reason"] == "reauth_wrong_account"


async def test_local_reauth_success(hass: HomeAssistant) -> None:
    """Test reauthentication flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        version=2,
        data={
            "username": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "hub": TEST_SERVER,
            "host": TEST_HOST,
            "api_type": "local",
        },
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
    assert result["step_id"] == "local_or_cloud"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "local"},
    )

    assert result2["step_id"] == "local"

    with patch.multiple(
        "pyoverkiz.client.OverkizClient",
        login=AsyncMock(return_value=True),
        get_gateways=AsyncMock(return_value=MOCK_GATEWAY_RESPONSE),
        get_setup_option=AsyncMock(return_value=True),
        generate_local_token=AsyncMock(return_value="1234123412341234"),
        activate_local_token=AsyncMock(return_value=True),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD2,
            },
        )

        assert result3["type"] == data_entry_flow.FlowResultType.ABORT
        assert result3["reason"] == "reauth_successful"
        assert mock_entry.data["username"] == TEST_EMAIL
        assert mock_entry.data["password"] == TEST_PASSWORD2


async def test_local_reauth_wrong_account(hass: HomeAssistant) -> None:
    """Test reauthentication flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID2,
        version=2,
        data={
            "username": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "hub": TEST_SERVER,
            "host": TEST_HOST,
            "api_type": "local",
        },
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
    assert result["step_id"] == "local_or_cloud"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "local"},
    )

    assert result2["step_id"] == "local"

    with patch.multiple(
        "pyoverkiz.client.OverkizClient",
        login=AsyncMock(return_value=True),
        get_gateways=AsyncMock(return_value=MOCK_GATEWAY_RESPONSE),
        get_setup_option=AsyncMock(return_value=True),
        generate_local_token=AsyncMock(return_value="1234123412341234"),
        activate_local_token=AsyncMock(return_value=True),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD2,
            },
        )

        assert result3["type"] == data_entry_flow.FlowResultType.ABORT
        assert result3["reason"] == "reauth_wrong_account"


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

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER},
    )

    assert result2["type"] == "form"
    assert result2["step_id"] == "local_or_cloud"

    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "cloud"},
    )

    with patch("pyoverkiz.client.OverkizClient.login", return_value=True), patch(
        "pyoverkiz.client.OverkizClient.get_gateways", return_value=None
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD,
            },
        )

    assert result4["type"] == "create_entry"
    assert result4["title"] == TEST_EMAIL
    assert result4["data"] == {
        "username": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "hub": TEST_SERVER,
        "api_type": "cloud",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_flow_already_configured(hass: HomeAssistant) -> None:
    """Test that DHCP doesn't setup already configured gateways."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD, "hub": TEST_SERVER},
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

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER},
    )

    assert result2["type"] == "form"
    assert result2["step_id"] == "local_or_cloud"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "cloud"},
    )

    assert result3["type"] == "form"
    assert result3["step_id"] == "cloud"

    with patch("pyoverkiz.client.OverkizClient.login", return_value=True), patch(
        "pyoverkiz.client.OverkizClient.get_gateways",
        return_value=MOCK_GATEWAY_RESPONSE,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    assert result4["type"] == "create_entry"
    assert result4["title"] == TEST_EMAIL
    assert result4["data"] == {
        "username": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "hub": TEST_SERVER,
        "api_type": "cloud",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_local_zeroconf_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that zeroconf discovery for new local bridge works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=FAKE_ZERO_CONF_INFO_LOCAL,
        context={"source": config_entries.SOURCE_ZEROCONF},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER},
    )

    assert result2["type"] == "form"
    assert result2["step_id"] == "local_or_cloud"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "local"},
    )

    assert result3["type"] == "form"
    assert result3["step_id"] == "local"

    with patch.multiple(
        "pyoverkiz.client.OverkizClient",
        login=AsyncMock(return_value=True),
        get_gateways=AsyncMock(return_value=MOCK_GATEWAY_RESPONSE),
        get_setup_option=AsyncMock(return_value=True),
        generate_local_token=AsyncMock(return_value="1234123412341234"),
        activate_local_token=AsyncMock(return_value=True),
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD, "verify_ssl": False},
        )

    assert result4["type"] == "create_entry"
    assert result4["title"] == "gateway-1234-5678-9123.local:8443"
    assert result4["data"] == {
        "username": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "hub": TEST_SERVER,
        "host": "gateway-1234-5678-9123.local:8443",
        "api_type": "local",
        "token": "1234123412341234",
        "verify_ssl": False,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_flow_already_configured(hass: HomeAssistant) -> None:
    """Test that zeroconf doesn't setup already configured gateways."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD, "hub": TEST_SERVER},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=FAKE_ZERO_CONF_INFO,
        context={"source": config_entries.SOURCE_ZEROCONF},
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"

"""Tests for Overkiz config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientConnectorCertificateError, ClientError
from pyoverkiz.client import GatewayCandidate
from pyoverkiz.const import (
    REXEL_OAUTH_AUTHORIZE_URL,
    REXEL_OAUTH_POLICY,
    REXEL_OAUTH_SCOPE,
    REXEL_OAUTH_TOKEN_URL,
)
from pyoverkiz.exceptions import (
    ApplicationNotAllowedError,
    BadCredentialsError,
    MaintenanceError,
    NoSuchTokenError,
    TooManyAttemptsBannedError,
    TooManyRequestsError,
    UnknownUserError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.overkiz.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

REXEL_CLIENT_ID = "1234"
REXEL_REDIRECT_URI = "https://example.com/auth/external/callback"

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
TEST_TOKEN = "1234123412341234"

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

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "cloud"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud"

    with (
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.login",
            return_value=True,
        ),
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.get_gateways",
            return_value=MOCK_GATEWAY_RESPONSE,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
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

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER2},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud"

    with (
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.login",
            return_value=True,
        ),
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.get_gateways",
            return_value=MOCK_GATEWAY_RESPONSE,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_local_happy_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test local API configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "local"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local"

    with patch.multiple(
        "homeassistant.components.overkiz.config_flow.OverkizClient",
        login=AsyncMock(return_value=True),
        get_gateways=AsyncMock(return_value=MOCK_GATEWAY_RESPONSE),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "gateway-1234-5678-1234.local:8443",
                "token": TEST_TOKEN,
                "verify_ssl": True,
            },
        )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "gateway-1234-5678-1234.local:8443"
    assert result["data"] == {
        "host": "gateway-1234-5678-1234.local:8443",
        "token": TEST_TOKEN,
        "verify_ssl": True,
        "hub": TEST_SERVER,
        "api_type": "local",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (BadCredentialsError, "invalid_auth"),
        (TooManyRequestsError, "too_many_requests"),
        (TimeoutError, "cannot_connect"),
        (ClientError, "cannot_connect"),
        (MaintenanceError, "server_in_maintenance"),
        (TooManyAttemptsBannedError, "too_many_attempts"),
        (UnknownUserError, "unsupported_hardware"),
        (ApplicationNotAllowedError, "application_not_allowed"),
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

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "cloud"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud"

    with patch(
        "homeassistant.components.overkiz.config_flow.OverkizClient.login",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


@pytest.mark.parametrize(
    ("side_effect", "description_placeholder", "server"),
    [
        (UnknownUserError, "CozyTouch", TEST_SERVER_COZYTOUCH),
        (UnknownUserError, "Unknown", TEST_SERVER2),
    ],
)
async def test_form_invalid_hardware_cloud(
    hass: HomeAssistant,
    side_effect: Exception,
    description_placeholder: str,
    server: str,
) -> None:
    """Test we handle unsupported hardware (cloud)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": server},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud"

    with patch(
        "homeassistant.components.overkiz.config_flow.OverkizClient.login",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unsupported_hardware"}
    assert result["description_placeholders"] == {
        "unsupported_device": description_placeholder
    }


@pytest.mark.parametrize(
    ("side_effect", "description_placeholder", "server"),
    [
        (UnknownUserError, "Somfy Protect", TEST_SERVER),
    ],
)
async def test_form_invalid_hardware_cloud_local(
    hass: HomeAssistant,
    side_effect: Exception,
    description_placeholder: str,
    server: str,
) -> None:
    """Test we handle unsupported hardware (cloud and local)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": server},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "cloud"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud"

    with patch(
        "homeassistant.components.overkiz.config_flow.OverkizClient.login",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unsupported_hardware"}
    assert result["description_placeholders"] == {
        "unsupported_device": description_placeholder
    }


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (BadCredentialsError, "invalid_auth"),
        (TooManyRequestsError, "too_many_requests"),
        (
            ClientConnectorCertificateError(Mock(host=TEST_HOST), Exception),
            "certificate_verify_failed",
        ),
        (TimeoutError, "cannot_connect"),
        (ClientError, "cannot_connect"),
        (MaintenanceError, "server_in_maintenance"),
        (TooManyAttemptsBannedError, "too_many_attempts"),
        (UnknownUserError, "unsupported_hardware"),
        (NoSuchTokenError, "invalid_auth"),
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

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "local"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local"

    with patch(
        "homeassistant.components.overkiz.config_flow.OverkizClient.login",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": TEST_HOST,
                "token": TEST_TOKEN,
                "verify_ssl": True,
            },
        )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (BadCredentialsError, "unsupported_hardware"),
    ],
)
async def test_form_invalid_cozytouch_auth(
    hass: HomeAssistant, side_effect: Exception, error: str
) -> None:
    """Test we handle invalid auth (cloud)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER_COZYTOUCH},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud"

    with patch(
        "homeassistant.components.overkiz.config_flow.OverkizClient.login",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert result["step_id"] == "cloud"


async def test_cloud_abort_on_duplicate_entry(hass: HomeAssistant) -> None:
    """Test we get the form."""

    MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD, "hub": TEST_SERVER},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "cloud"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud"

    with (
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.login",
            return_value=True,
        ),
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.get_gateways",
            return_value=MOCK_GATEWAY_RESPONSE,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_local_abort_on_duplicate_entry(hass: HomeAssistant) -> None:
    """Test local API configuration is aborted if gateway already exists."""

    MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        version=2,
        data={
            "host": TEST_HOST,
            "token": TEST_TOKEN,
            "verify_ssl": True,
            "hub": TEST_SERVER,
            "api_type": "local",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "local"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local"

    with patch.multiple(
        "homeassistant.components.overkiz.config_flow.OverkizClient",
        login=AsyncMock(return_value=True),
        get_gateways=AsyncMock(return_value=MOCK_GATEWAY_RESPONSE),
        get_setup_option=AsyncMock(return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": TEST_HOST,
                "token": TEST_TOKEN,
                "verify_ssl": True,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_cloud_allow_multiple_unique_entries(hass: HomeAssistant) -> None:
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

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "cloud"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud"

    with (
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.login",
            return_value=True,
        ),
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.get_gateways",
            return_value=MOCK_GATEWAY_RESPONSE,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_EMAIL
    assert result["data"] == {
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

    result = await mock_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud"

    with (
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.login",
            return_value=True,
        ),
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.get_gateways",
            return_value=MOCK_GATEWAY_RESPONSE,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD2,
            },
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
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

    result = await mock_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud"

    with (
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.login",
            return_value=True,
        ),
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.get_gateways",
            return_value=MOCK_GATEWAY2_RESPONSE,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD2,
            },
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_wrong_account"


async def test_local_reauth_legacy(hass: HomeAssistant) -> None:
    """Test legacy reauthentication flow with username/password."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        version=2,
        data={
            "host": TEST_HOST,
            "username": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "verify_ssl": True,
            "hub": TEST_SERVER,
            "api_type": "local",
        },
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "local"},
    )

    assert result2["step_id"] == "local"

    with patch.multiple(
        "homeassistant.components.overkiz.config_flow.OverkizClient",
        login=AsyncMock(return_value=True),
        get_gateways=AsyncMock(return_value=MOCK_GATEWAY_RESPONSE),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": TEST_HOST,
                "token": "new_token",
                "verify_ssl": True,
            },
        )

        assert result3["type"] is FlowResultType.ABORT
        assert result3["reason"] == "reauth_successful"
        assert mock_entry.data["host"] == TEST_HOST
        assert mock_entry.data["token"] == "new_token"
        assert mock_entry.data["verify_ssl"] is True
        # The legacy username/password are dropped after migrating to a token.
        assert "username" not in mock_entry.data
        assert "password" not in mock_entry.data


async def test_local_reauth_success(hass: HomeAssistant) -> None:
    """Test modern local reauth flow."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        version=2,
        data={
            "host": TEST_HOST,
            "token": "old_token",
            "verify_ssl": True,
            "hub": TEST_SERVER,
            "api_type": "local",
        },
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "local"},
    )

    assert result2["step_id"] == "local"

    with patch.multiple(
        "homeassistant.components.overkiz.config_flow.OverkizClient",
        login=AsyncMock(return_value=True),
        get_gateways=AsyncMock(return_value=MOCK_GATEWAY_RESPONSE),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": TEST_HOST,
                "token": "new_token",
                "verify_ssl": True,
            },
        )

        assert result3["type"] is FlowResultType.ABORT
        assert result3["reason"] == "reauth_successful"
        assert mock_entry.data["host"] == TEST_HOST
        assert mock_entry.data["token"] == "new_token"
        assert mock_entry.data["verify_ssl"] is True
        assert "username" not in mock_entry.data
        assert "password" not in mock_entry.data


async def test_local_reauth_wrong_account(hass: HomeAssistant) -> None:
    """Test local reauth flow with wrong gateway account."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID2,
        version=2,
        data={
            "host": TEST_HOST,
            "token": "old_token",
            "verify_ssl": True,
            "hub": TEST_SERVER,
            "api_type": "local",
        },
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "local"},
    )

    assert result2["step_id"] == "local"

    with patch.multiple(
        "homeassistant.components.overkiz.config_flow.OverkizClient",
        login=AsyncMock(return_value=True),
        get_gateways=AsyncMock(return_value=MOCK_GATEWAY_RESPONSE),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": TEST_HOST,
                "token": "new_token",
                "verify_ssl": True,
            },
        )

        assert result3["type"] is FlowResultType.ABORT
        assert result3["reason"] == "reauth_wrong_account"


async def test_cloud_reconfigure_success(hass: HomeAssistant) -> None:
    """Test reconfiguration flow on a cloud entry."""
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

    result = await mock_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud"

    with (
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.login",
            return_value=True,
        ),
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.get_gateways",
            return_value=MOCK_GATEWAY_RESPONSE,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD2,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_entry.data["username"] == TEST_EMAIL
    assert mock_entry.data["password"] == TEST_PASSWORD2


async def test_cloud_reconfigure_wrong_account(hass: HomeAssistant) -> None:
    """Test reconfiguration aborts when the gateway account differs."""
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

    result = await mock_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud"

    with (
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.login",
            return_value=True,
        ),
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.get_gateways",
            return_value=MOCK_GATEWAY2_RESPONSE,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD2,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_wrong_account"


async def test_local_reconfigure_success(hass: HomeAssistant) -> None:
    """Test reconfiguration flow on a local entry."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        version=2,
        data={
            "host": TEST_HOST,
            "token": "old_token",
            "verify_ssl": True,
            "hub": TEST_SERVER,
            "api_type": "local",
        },
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "local"},
    )

    assert result["step_id"] == "local"

    with patch.multiple(
        "homeassistant.components.overkiz.config_flow.OverkizClient",
        login=AsyncMock(return_value=True),
        get_gateways=AsyncMock(return_value=MOCK_GATEWAY_RESPONSE),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": TEST_HOST,
                "token": "new_token",
                "verify_ssl": True,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_entry.data["host"] == TEST_HOST
    assert mock_entry.data["token"] == "new_token"
    assert mock_entry.data["verify_ssl"] is True


async def test_local_reconfigure_wrong_account(hass: HomeAssistant) -> None:
    """Test local reconfiguration aborts when the gateway account differs."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID2,
        version=2,
        data={
            "host": TEST_HOST,
            "token": "old_token",
            "verify_ssl": True,
            "hub": TEST_SERVER,
            "api_type": "local",
        },
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "local"},
    )

    assert result["step_id"] == "local"

    with patch.multiple(
        "homeassistant.components.overkiz.config_flow.OverkizClient",
        login=AsyncMock(return_value=True),
        get_gateways=AsyncMock(return_value=MOCK_GATEWAY_RESPONSE),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": TEST_HOST,
                "token": "new_token",
                "verify_ssl": True,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_wrong_account"


async def test_reconfigure_switch_cloud_to_local(hass: HomeAssistant) -> None:
    """Test reconfiguring a cloud entry to use the local API."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        version=2,
        data={
            "username": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "hub": TEST_SERVER,
            "api_type": "cloud",
        },
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "local"},
    )

    assert result["step_id"] == "local"

    with patch.multiple(
        "homeassistant.components.overkiz.config_flow.OverkizClient",
        login=AsyncMock(return_value=True),
        get_gateways=AsyncMock(return_value=MOCK_GATEWAY_RESPONSE),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": TEST_HOST,
                "token": TEST_TOKEN,
                "verify_ssl": True,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_entry.data["api_type"] == "local"
    assert mock_entry.data["host"] == TEST_HOST
    assert mock_entry.data["token"] == TEST_TOKEN
    # Full data replace drops the previous cloud credentials.
    assert "username" not in mock_entry.data
    assert "password" not in mock_entry.data


async def test_dhcp_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test that DHCP discovery for new bridge works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=DhcpServiceInfo(
            hostname="gateway-1234-5678-9123",
            ip="192.168.1.4",
            macaddress="f8811a000000",
        ),
        context={"source": config_entries.SOURCE_DHCP},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "cloud"},
    )

    with (
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.login",
            return_value=True,
        ),
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.get_gateways",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_EMAIL
    assert result["data"] == {
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
        data=DhcpServiceInfo(
            hostname="gateway-1234-5678-9123",
            ip="192.168.1.4",
            macaddress="f8811a000000",
        ),
        context={"source": config_entries.SOURCE_DHCP},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test that zeroconf discovery for new bridge works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=FAKE_ZERO_CONF_INFO,
        context={"source": config_entries.SOURCE_ZEROCONF},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "cloud"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud"

    with (
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.login",
            return_value=True,
        ),
        patch(
            "homeassistant.components.overkiz.config_flow.OverkizClient.get_gateways",
            return_value=MOCK_GATEWAY_RESPONSE,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_EMAIL
    assert result["data"] == {
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "local"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local"

    with patch.multiple(
        "homeassistant.components.overkiz.config_flow.OverkizClient",
        login=AsyncMock(return_value=True),
        get_gateways=AsyncMock(return_value=MOCK_GATEWAY_RESPONSE),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "gateway-1234-5678-9123.local:8443",
                "token": TEST_TOKEN,
                "verify_ssl": False,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "gateway-1234-5678-9123.local:8443"

    # Verify no username/password in data
    assert result["data"] == {
        "host": "gateway-1234-5678-9123.local:8443",
        "token": TEST_TOKEN,
        "verify_ssl": False,
        "hub": TEST_SERVER,
        "api_type": "local",
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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_local_zeroconf_flow_updates_host(hass: HomeAssistant) -> None:
    """Test that rediscovery of a local gateway refreshes the stored host."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        data={
            "host": "gateway-1234-5678-9123.local:9999",
            "token": TEST_TOKEN,
            "verify_ssl": False,
            "hub": TEST_SERVER,
            "api_type": "local",
        },
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=FAKE_ZERO_CONF_INFO_LOCAL,
        context={"source": config_entries.SOURCE_ZEROCONF},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data["host"] == "gateway-1234-5678-9123.local:8443"


@pytest.fixture
async def setup_rexel_credentials(hass: HomeAssistant) -> None:
    """Set up the application credential used by the Rexel OAuth2 flow."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(REXEL_CLIENT_ID, ""),
        DOMAIN,
    )


async def _async_rexel_oauth_external_step(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    flow_id: str,
) -> None:
    """Drive the OAuth2 external step and stub the token exchange."""
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {"flow_id": flow_id, "redirect_uri": REXEL_REDIRECT_URI},
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200

    aioclient_mock.post(
        REXEL_OAUTH_TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )


@pytest.mark.usefixtures("current_request_with_host", "setup_rexel_credentials")
async def test_rexel_full_flow_single_gateway(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
) -> None:
    """A single-gateway Rexel account auto-selects and creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Rexel is part of SERVERS_WITH_LOCAL_API, so the local/cloud choice is
    # shown before the OAuth2 flow starts.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"hub": "rexel"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_type": "cloud"}
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert REXEL_OAUTH_AUTHORIZE_URL in result["url"]
    # Azure AD B2C needs the policy on the authorize URL; the helper rebuilds
    # the query string, so it must survive via extra_authorize_data.
    assert f"p={REXEL_OAUTH_POLICY}" in result["url"]
    # offline_access is required for B2C to return a refresh token.
    assert f"{REXEL_OAUTH_SCOPE}+offline_access" in result["url"]

    await _async_rexel_oauth_external_step(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"]
    )

    with patch(
        "homeassistant.components.overkiz.config_flow.OverkizClient.discover_gateways",
        return_value=[GatewayCandidate(gateway_id=TEST_GATEWAY_ID, label="My Home")],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Home"
    assert result["result"].unique_id == TEST_GATEWAY_ID
    assert result["data"]["hub"] == "rexel"
    assert result["data"]["gateway_id"] == TEST_GATEWAY_ID
    assert "token" in result["data"]
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host")
async def test_rexel_flow_reimports_removed_credential(
    hass: HomeAssistant,
) -> None:
    """The Rexel flow re-imports its client credential if the user removed it."""
    assert await async_setup_component(hass, "application_credentials", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"hub": "rexel"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_type": "cloud"}
    )

    # Reaching the OAuth2 external step proves an implementation was available,
    # i.e. the credential was re-imported despite not being present beforehand.
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert REXEL_OAUTH_AUTHORIZE_URL in result["url"]


@pytest.mark.usefixtures("current_request_with_host", "setup_rexel_credentials")
async def test_rexel_full_flow_multiple_gateways(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
) -> None:
    """A multi-gateway Rexel account shows a selection step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"hub": "rexel"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_type": "cloud"}
    )
    await _async_rexel_oauth_external_step(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"]
    )

    with patch(
        "homeassistant.components.overkiz.config_flow.OverkizClient.discover_gateways",
        return_value=[
            GatewayCandidate(gateway_id=TEST_GATEWAY_ID, label="Home"),
            GatewayCandidate(gateway_id=TEST_GATEWAY_ID2, label="Office"),
        ],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_gateway"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"gateway_id": TEST_GATEWAY_ID2}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Office"
    assert result["result"].unique_id == TEST_GATEWAY_ID2
    assert result["data"]["gateway_id"] == TEST_GATEWAY_ID2
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host", "setup_rexel_credentials")
async def test_rexel_flow_no_gateways(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A Rexel account without gateways aborts."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"hub": "rexel"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_type": "cloud"}
    )
    await _async_rexel_oauth_external_step(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"]
    )

    with patch(
        "homeassistant.components.overkiz.config_flow.OverkizClient.discover_gateways",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_gateways"


@pytest.mark.usefixtures("current_request_with_host", "setup_rexel_credentials")
async def test_rexel_flow_cannot_connect(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A Rexel gateway discovery error aborts."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"hub": "rexel"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_type": "cloud"}
    )
    await _async_rexel_oauth_external_step(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"]
    )

    with patch(
        "homeassistant.components.overkiz.config_flow.OverkizClient.discover_gateways",
        side_effect=ClientError,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("current_request_with_host", "setup_rexel_credentials")
async def test_rexel_reauth_wrong_account(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_rexel_config_entry: MockConfigEntry,
) -> None:
    """Reauth with a different Rexel gateway aborts."""
    mock_rexel_config_entry.add_to_hass(hass)

    # Reauth carries the stored hub, so the flow skips the server picker and
    # goes to the local/cloud choice before re-running the OAuth2 flow.
    result = await mock_rexel_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_type": "cloud"}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    await _async_rexel_oauth_external_step(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"]
    )

    with patch(
        "homeassistant.components.overkiz.config_flow.OverkizClient.discover_gateways",
        return_value=[GatewayCandidate(gateway_id=TEST_GATEWAY_ID2, label="Other")],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_wrong_account"


@pytest.mark.usefixtures("current_request_with_host", "setup_rexel_credentials")
async def test_rexel_reauth_success(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_rexel_config_entry: MockConfigEntry,
) -> None:
    """Reauth with the same Rexel gateway updates the entry and reloads."""
    mock_rexel_config_entry.add_to_hass(hass)

    result = await mock_rexel_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_type": "cloud"}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    await _async_rexel_oauth_external_step(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"]
    )

    with patch(
        "homeassistant.components.overkiz.config_flow.OverkizClient.discover_gateways",
        return_value=[GatewayCandidate(gateway_id=TEST_GATEWAY_ID, label="My Home")],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_rexel_config_entry.data["token"]["access_token"] == "mock-access-token"


@pytest.mark.usefixtures("current_request_with_host", "setup_rexel_credentials")
async def test_rexel_reconfigure_wrong_account(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_rexel_config_entry: MockConfigEntry,
) -> None:
    """Reconfigure with a different Rexel gateway aborts."""
    mock_rexel_config_entry.add_to_hass(hass)

    # Reconfigure carries the stored hub, so the flow skips the server picker
    # and goes to the local/cloud choice before re-running the OAuth2 flow.
    result = await mock_rexel_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_type": "cloud"}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    await _async_rexel_oauth_external_step(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"]
    )

    with patch(
        "homeassistant.components.overkiz.config_flow.OverkizClient.discover_gateways",
        return_value=[GatewayCandidate(gateway_id=TEST_GATEWAY_ID2, label="Other")],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_wrong_account"


@pytest.mark.usefixtures("current_request_with_host", "setup_rexel_credentials")
async def test_rexel_reconfigure_success(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_rexel_config_entry: MockConfigEntry,
) -> None:
    """Reconfigure with the same Rexel gateway updates the entry and reloads."""
    mock_rexel_config_entry.add_to_hass(hass)

    result = await mock_rexel_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_or_cloud"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_type": "cloud"}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    await _async_rexel_oauth_external_step(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"]
    )

    with patch(
        "homeassistant.components.overkiz.config_flow.OverkizClient.discover_gateways",
        return_value=[GatewayCandidate(gateway_id=TEST_GATEWAY_ID, label="My Home")],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_rexel_config_entry.data["token"]["access_token"] == "mock-access-token"

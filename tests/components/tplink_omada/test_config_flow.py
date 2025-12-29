"""Test the TP-Link Omada config flows."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tplink_omada_client import OmadaSite
from tplink_omada_client.exceptions import (
    ConnectionFailed,
    LoginFailed,
    OmadaClientException,
    UnsupportedControllerVersion,
)

from homeassistant import config_entries
from homeassistant.components.tplink_omada.config_flow import (
    _validate_input,
    create_omada_client,
)
from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_USER_DATA = {
    "host": "https://fake.omada.host",
    "verify_ssl": True,
    "username": "test-username",
    "password": "test-password",
}

MOCK_ENTRY_DATA = {
    "host": "https://fake.omada.host",
    "verify_ssl": True,
    "site": "SiteId",
    "username": "test-username",
    "password": "test-password",
}


@pytest.fixture
def mock_config_flow_client() -> Generator[MagicMock]:
    """Mock Omada client for config flow testing."""
    with patch(
        "homeassistant.components.tplink_omada.config_flow.create_omada_client",
        autospec=True,
    ) as client_mock:
        client = client_mock.return_value
        # Set default return values for the client methods
        client.login = AsyncMock(return_value="omada_id")
        client.get_controller_name = AsyncMock(return_value="OC200")
        client.get_sites = AsyncMock(return_value=[])
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock]:
    """Mock async_setup_entry."""
    with patch(
        "homeassistant.components.tplink_omada.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


async def test_form_single_site(
    hass: HomeAssistant,
    mock_config_flow_client: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_config_flow_client.login.return_value = "omada_id"
    mock_config_flow_client.get_controller_name.return_value = "OC200"
    mock_config_flow_client.get_sites.return_value = [
        OmadaSite("Display Name", "SiteId")
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OC200 (Display Name)"
    assert result["data"] == MOCK_ENTRY_DATA
    assert result["result"].unique_id == "omada_id"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_multiple_sites(
    hass: HomeAssistant,
    mock_config_flow_client: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mock_config_flow_client.login.return_value = "omada_id"
    mock_config_flow_client.get_controller_name.return_value = "OC200"
    mock_config_flow_client.get_sites.return_value = [
        OmadaSite("Site 1", "first"),
        OmadaSite("Site 2", "second"),
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "site"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "site": "second",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OC200 (Site 2)"
    assert result["data"] == {
        "host": "https://fake.omada.host",
        "verify_ssl": True,
        "site": "second",
        "username": "test-username",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (LoginFailed(-1000, "Invalid username/password"), "invalid_auth"),
        (OmadaClientException(), "unknown"),
        (Exception("Generic error"), "unknown"),
        (UnsupportedControllerVersion("4.0.0"), "unsupported_controller"),
        (ConnectionFailed(), "cannot_connect"),
    ],
)
async def test_form_errors_and_recovery(
    hass: HomeAssistant,
    mock_config_flow_client: MagicMock,
    mock_setup_entry: MagicMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test we handle various errors and can recover to complete the flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First attempt: trigger the error
    mock_config_flow_client.login.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_DATA,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Second attempt: clear error and complete successfully
    mock_config_flow_client.login.side_effect = None
    mock_config_flow_client.login.return_value = "omada_id"
    mock_config_flow_client.get_controller_name.return_value = "OC200"
    mock_config_flow_client.get_sites.return_value = [
        OmadaSite("Display Name", "SiteId")
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OC200 (Display Name)"
    assert result["data"] == MOCK_ENTRY_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_no_sites(
    hass: HomeAssistant, mock_config_flow_client: MagicMock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_config_flow_client.login.return_value = "omada_id"
    mock_config_flow_client.get_controller_name.return_value = "OC200"
    mock_config_flow_client.get_sites.return_value = []

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_DATA,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_sites_found"}


@pytest.mark.parametrize(
    ("controller_id", "expected_reason"),
    [
        ("12345", "reauth_successful"),
        ("different_controller_id", "device_mismatch"),
    ],
)
async def test_async_step_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_flow_client: MagicMock,
    controller_id: str,
    expected_reason: str,
) -> None:
    """Test reauth flow with matching and mismatching controller IDs."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_config_flow_client.login.return_value = controller_id
    mock_config_flow_client.get_controller_name.return_value = "OC200"
    mock_config_flow_client.get_sites.return_value = [
        OmadaSite("Display Name", "SiteId")
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "new_uname", "password": "new_passwd"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (LoginFailed(-1000, "Invalid username/password"), "invalid_auth"),
        (OmadaClientException(), "unknown"),
        (Exception("Generic error"), "unknown"),
        (UnsupportedControllerVersion("4.0.0"), "unsupported_controller"),
        (ConnectionFailed(), "cannot_connect"),
    ],
)
async def test_async_step_reauth_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_flow_client: MagicMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test reauth handles various exceptions."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_config_flow_client.login.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "new_uname", "password": "new_passwd"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": expected_error}


async def test_validate_input(hass: HomeAssistant) -> None:
    """Test validate returns HubInfo."""

    with (
        patch(
            "tplink_omada_client.omadaclient.OmadaClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.tplink_omada.config_flow.create_omada_client",
            return_value=mock_client,
        ) as create_mock,
    ):
        mock_client.login.return_value = "Id"
        mock_client.get_controller_name.return_value = "Name"
        mock_client.get_sites.return_value = [OmadaSite("x", "y")]
        result = await _validate_input(hass, MOCK_USER_DATA)

    create_mock.assert_awaited_once()
    mock_client.login.assert_awaited_once()
    mock_client.get_controller_name.assert_awaited_once()
    mock_client.get_sites.assert_awaited_once()
    assert result.controller_id == "Id"
    assert result.name == "Name"
    assert result.sites == [OmadaSite("x", "y")]


async def test_create_omada_client_parses_args(hass: HomeAssistant) -> None:
    """Test config arguments are passed to Omada client."""

    with (
        patch(
            "homeassistant.components.tplink_omada.config_flow.OmadaClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.tplink_omada.config_flow.async_get_clientsession",
            return_value="ws",
        ) as mock_clientsession,
    ):
        result = await create_omada_client(hass, MOCK_USER_DATA)

    assert result is not None
    mock_client.assert_called_once_with(
        "https://fake.omada.host", "test-username", "test-password", "ws"
    )
    mock_clientsession.assert_called_once_with(hass, verify_ssl=True)


async def test_create_omada_client_adds_missing_scheme(hass: HomeAssistant) -> None:
    """Test config arguments are passed to Omada client."""

    with (
        patch(
            "homeassistant.components.tplink_omada.config_flow.OmadaClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.tplink_omada.config_flow.async_get_clientsession",
            return_value="ws",
        ) as mock_clientsession,
    ):
        result = await create_omada_client(
            hass,
            {
                "host": "fake.omada.host",
                "verify_ssl": True,
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result is not None
    mock_client.assert_called_once_with(
        "https://fake.omada.host", "test-username", "test-password", "ws"
    )
    mock_clientsession.assert_called_once_with(hass, verify_ssl=True)


async def test_create_omada_client_with_ip_creates_clientsession(
    hass: HomeAssistant,
) -> None:
    """Test config arguments are passed to Omada client."""

    with (
        patch(
            "homeassistant.components.tplink_omada.config_flow.OmadaClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.tplink_omada.config_flow.CookieJar", autospec=True
        ) as mock_jar,
        patch(
            "homeassistant.components.tplink_omada.config_flow.async_create_clientsession",
            return_value="ws",
        ) as mock_create_clientsession,
    ):
        result = await create_omada_client(
            hass,
            {
                "host": "10.10.10.10",
                "verify_ssl": True,
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result is not None
    mock_client.assert_called_once_with(
        "https://10.10.10.10", "test-username", "test-password", "ws"
    )
    mock_create_clientsession.assert_called_once_with(
        hass, cookie_jar=mock_jar.return_value, verify_ssl=True
    )

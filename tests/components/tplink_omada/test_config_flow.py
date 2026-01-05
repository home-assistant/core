"""Test the TP-Link Omada config flows."""

from unittest.mock import MagicMock, patch

import pytest
from tplink_omada_client import OmadaSite
from tplink_omada_client.exceptions import (
    ConnectionFailed,
    LoginFailed,
    OmadaClientException,
    UnsupportedControllerVersion,
)

from homeassistant.components.tplink_omada.config_flow import create_omada_client
from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
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


async def test_form_single_site(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_DATA,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OC200 (Display Name)"
    assert result["data"] == MOCK_ENTRY_DATA
    assert result["result"].unique_id == "12345"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_multiple_sites(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mock_omada_client.get_sites.return_value = [
        OmadaSite("Site 1", "first"),
        OmadaSite("Site 2", "second"),
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_DATA,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "site"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "site": "second",
        },
    )

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
    mock_omada_client: MagicMock,
    mock_setup_entry: MagicMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test we handle various errors and can recover to complete the flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # First attempt: trigger the error
    mock_omada_client.login.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_DATA,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Second attempt: clear error and complete successfully
    mock_omada_client.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_DATA,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OC200 (Display Name)"
    assert result["data"] == MOCK_ENTRY_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_no_sites(hass: HomeAssistant, mock_omada_client: MagicMock) -> None:
    """Test we handle the case when no sites are found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_omada_client.get_sites.return_value = []

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_DATA,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_sites_found"}

    mock_omada_client.get_sites.return_value = [OmadaSite("Display Name", "SiteId")]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_DATA,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


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
    mock_omada_client: MagicMock,
    controller_id: str,
    expected_reason: str,
) -> None:
    """Test reauth flow with matching and mismatching controller IDs."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_omada_client.login.return_value = controller_id

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "new_uname", CONF_PASSWORD: "new_passwd"}
    )

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
    mock_omada_client: MagicMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test reauth handles various exceptions."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_omada_client.login.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "new_uname", CONF_PASSWORD: "new_passwd"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": expected_error}

    mock_omada_client.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "new_uname", CONF_PASSWORD: "new_passwd"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


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

"""Test the INDI Allsky Config flow."""

import ssl
from unittest.mock import AsyncMock

from aioindiallsky import IndiAllSkyAuthError, IndiAllSkyConnectionError
import pytest

from homeassistant import config_entries
from homeassistant.components.indi_allsky.const import DOMAIN
from homeassistant.components.indi_allsky.util import get_ssl_context, normalize_host
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("host", "port", "ssl_enabled", "verify_ssl", "expected_title"),
    [
        pytest.param(
            "127.0.0.1",
            443,
            True,
            False,
            "INDI Allsky (127.0.0.1)",
            id="ipv4_default_port",
        ),
        pytest.param(
            "127.0.0.1",
            8443,
            True,
            True,
            "INDI Allsky (127.0.0.1:8443)",
            id="ipv4_custom_port",
        ),
        pytest.param(
            "2001:db8::1",
            443,
            True,
            True,
            "INDI Allsky (2001:db8::1)",
            id="ipv6_default_port",
        ),
        pytest.param(
            "2001:db8::1",
            8080,
            False,
            True,
            "INDI Allsky (2001:db8::1:8080)",
            id="ipv6_custom_port",
        ),
    ],
)
async def test_form_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_indi_allsky_client: AsyncMock,
    host: str,
    port: int,
    ssl_enabled: bool,
    verify_ssl: bool,
    expected_title: str,
) -> None:
    """Test we get the form, validate the client, and create a successful entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_SSL: ssl_enabled,
            CONF_VERIFY_SSL: verify_ssl,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title
    assert result["data"] == {
        CONF_HOST: host,
        CONF_PORT: port,
        CONF_SSL: ssl_enabled,
        CONF_VERIFY_SSL: verify_ssl,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error_key"),
    [
        (IndiAllSkyConnectionError("Cannot connect"), "cannot_connect"),
        (IndiAllSkyAuthError("Invalid key"), "invalid_auth"),
        (Exception("Unexpected error"), "unknown"),
    ],
)
async def test_form_failures_and_recovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_indi_allsky_client: AsyncMock,
    side_effect: Exception,
    error_key: str,
) -> None:
    """Test handling validation failures and ensuring the flow can recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_indi_allsky_client.fetch_image.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 443,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}

    mock_indi_allsky_client.fetch_image.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 443,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "duplicate_host",
    [
        "127.0.0.1",
        " 127.0.0.1 ",
    ],
)
async def test_form_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    duplicate_host: str,
) -> None:
    """Test duplicate host/port configurations abort early."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: duplicate_host,
            CONF_PORT: 443,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "duplicate_host",
    [
        "2001:db8::1",
        "[2001:db8::1]",
        "2001:0db8:0000:0000:0000:0000:0000:0001",
        "2001:DB8::1",
        " [2001:db8::1] ",
    ],
)
async def test_form_already_configured_ipv6(
    hass: HomeAssistant,
    duplicate_host: str,
) -> None:
    """Test duplicate IPv6 configurations abort regardless of formatting variation."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="INDI Allsky (2001:db8::1)",
        data={
            CONF_HOST: "2001:db8::1",
            CONF_PORT: 443,
        },
        entry_id="ipv6_entry",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: duplicate_host,
            CONF_PORT: 443,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("input_host", "expected_host"),
    [
        ("127.0.0.1", "127.0.0.1"),
        (" 127.0.0.1 ", "127.0.0.1"),
        ("allsky.local", "allsky.local"),
        ("2001:db8::1", "2001:db8::1"),
        ("[2001:db8::1]", "2001:db8::1"),
        ("2001:0db8:0000:0000:0000:0000:0000:0001", "2001:db8::1"),
        ("2001:DB8::1", "2001:db8::1"),
        (" [2001:db8::1] ", "2001:db8::1"),
    ],
)
def test_normalize_host(input_host: str, expected_host: str) -> None:
    """Test host normalization for IPv4, IPv6, and hostnames."""
    assert normalize_host(input_host) == expected_host


def test_get_ssl_context() -> None:
    """Test get_ssl_context return values for various SSL setting combinations."""
    assert get_ssl_context(ssl_enabled=False, verify_ssl=True) is False
    assert get_ssl_context(ssl_enabled=False, verify_ssl=False) is False

    ctx_verified = get_ssl_context(ssl_enabled=True, verify_ssl=True)
    assert isinstance(ctx_verified, ssl.SSLContext)
    assert ctx_verified.verify_mode != ssl.CERT_NONE

    ctx_no_verify = get_ssl_context(ssl_enabled=True, verify_ssl=False)
    assert isinstance(ctx_no_verify, ssl.SSLContext)
    assert ctx_no_verify.verify_mode == ssl.CERT_NONE


async def test_form_with_credentials_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test user step creates entry with credentials when username and password are provided."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 443,
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "INDI Allsky (127.0.0.1)"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 443,
        CONF_SSL: True,
        CONF_VERIFY_SSL: True,
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "credentials_input",
    [
        {CONF_USERNAME: "test_user"},
        {CONF_PASSWORD: "test_password"},
    ],
)
async def test_form_missing_credentials_failure(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    credentials_input: dict[str, str],
) -> None:
    """Test entering only username or only password yields missing_credentials error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    user_input = {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 443,
        **credentials_input,
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "missing_credentials"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 443,
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 443,
        CONF_SSL: True,
        CONF_VERIFY_SSL: True,
        CONF_USERNAME: "test-user",
        CONF_PASSWORD: "test-password",
    }


async def test_reauth_successful(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful re-authentication updates the config entry data."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "updated_user",
            CONF_PASSWORD: "updated_password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_USERNAME] == "updated_user"
    assert mock_config_entry.data[CONF_PASSWORD] == "updated_password"


@pytest.mark.parametrize(
    ("side_effect", "error_key"),
    [
        (IndiAllSkyAuthError("Invalid credentials"), "invalid_auth"),
        (IndiAllSkyConnectionError("Cannot connect"), "cannot_connect"),
        (Exception("Unexpected"), "unknown"),
    ],
)
async def test_reauth_failures(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    error_key: str,
) -> None:
    """Test reauth errors and subsequent recovery."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_indi_allsky_client.fetch_image.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "new_user",
            CONF_PASSWORD: "new_password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}

    mock_indi_allsky_client.fetch_image.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "new_user",
            CONF_PASSWORD: "new_password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_USERNAME] == "new_user"
    assert mock_config_entry.data[CONF_PASSWORD] == "new_password"

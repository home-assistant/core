"""Test the INDI Allsky Config flow."""

import ssl
from unittest.mock import AsyncMock, patch

from aioindiallsky import IndiAllSkyAuthError, IndiAllSkyConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry

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
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo


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
    assert result["result"].unique_id is None
    assert result["title"] == expected_title
    assert result["data"] == {
        CONF_HOST: host,
        CONF_PORT: port,
        CONF_SSL: ssl_enabled,
        CONF_VERIFY_SSL: verify_ssl,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (IndiAllSkyConnectionError("Cannot connect"), "cannot_connect"),
        (IndiAllSkyAuthError("Invalid credentials"), "invalid_auth"),
        (RuntimeError("Unexpected error"), "unknown"),
    ],
)
async def test_form_failures_and_recovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_indi_allsky_client: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test error handling on failed connections, auth errors, or unknown exceptions."""
    mock_indi_allsky_client.fetch_image.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 443,
            CONF_SSL: True,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Recover from the failure
    mock_indi_allsky_client.fetch_image.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 443,
            CONF_SSL: True,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id is None
    assert result["title"] == "INDI Allsky (127.0.0.1)"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate host and port configuration aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "127.0.0.1",
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


@pytest.mark.parametrize(
    (
        "discovery_info",
        "expected_ssl",
        "expected_port",
        "expected_title",
        "expected_unique_id",
    ),
    [
        (
            ZeroconfServiceInfo(
                ip_address="192.168.1.50",
                ip_addresses=["192.168.1.50"],
                port=443,
                hostname="indi-allsky.local.",
                type="_indi-allsky._tcp.local.",
                name="INDI Allsky._indi-allsky._tcp.local.",
                properties={
                    "path": "/indi-allsky",
                    "ssl": "true",
                    "mac": "aa:bb:cc:dd:ee:ff",
                },
            ),
            True,
            443,
            "INDI Allsky (192.168.1.50)",
            "aa:bb:cc:dd:ee:ff",
        ),
        (
            ZeroconfServiceInfo(
                ip_address="192.168.1.50",
                ip_addresses=["192.168.1.50"],
                port=8443,
                hostname="indi-allsky.local.",
                type="_indi-allsky._tcp.local.",
                name="INDI Allsky._indi-allsky._tcp.local.",
                properties={
                    "path": "/indi-allsky",
                    "ssl": "true",
                    "mac": "AA-BB-CC-DD-EE-FF",
                },
            ),
            True,
            8443,
            "INDI Allsky (192.168.1.50:8443)",
            "aa:bb:cc:dd:ee:ff",
        ),
        (
            ZeroconfServiceInfo(
                ip_address="192.168.1.50",
                ip_addresses=["192.168.1.50"],
                port=80,
                hostname="indi-allsky.local.",
                type="_indi-allsky._tcp.local.",
                name="INDI Allsky._indi-allsky._tcp.local.",
                properties={"path": "/indi-allsky", "ssl": "false"},
            ),
            False,
            80,
            "INDI Allsky (192.168.1.50)",
            None,
        ),
        (
            ZeroconfServiceInfo(
                ip_address="192.168.1.50",
                ip_addresses=["192.168.1.50"],
                port=None,
                hostname="indi-allsky.local.",
                type="_indi-allsky._tcp.local.",
                name="INDI Allsky._indi-allsky._tcp.local.",
                properties={"path": "/indi-allsky"},
            ),
            True,
            443,
            "INDI Allsky (192.168.1.50)",
            None,
        ),
    ],
)
async def test_zeroconf_discovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_indi_allsky_client: AsyncMock,
    discovery_info: ZeroconfServiceInfo,
    expected_ssl: bool,
    expected_port: int,
    expected_title: str,
    expected_unique_id: str | None,
) -> None:
    """Test discovering an INDI Allsky server via Zeroconf."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"] == {"name": "INDI Allsky"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == expected_unique_id
    assert result["title"] == expected_title
    assert result["data"] == {
        CONF_HOST: "192.168.1.50",
        CONF_PORT: expected_port,
        CONF_SSL: expected_ssl,
        CONF_VERIFY_SSL: True,
    }


async def test_zeroconf_cannot_connect(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test Zeroconf discovery aborts if server connection check fails."""
    mock_indi_allsky_client.fetch_image.side_effect = IndiAllSkyConnectionError(
        "Cannot connect"
    )

    discovery_info = ZeroconfServiceInfo(
        ip_address="192.168.1.50",
        ip_addresses=["192.168.1.50"],
        port=443,
        hostname="indi-allsky.local.",
        type="_indi-allsky._tcp.local.",
        name="INDI Allsky._indi-allsky._tcp.local.",
        properties={"path": "/indi-allsky", "mac": "aa:bb:cc:dd:ee:ff"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_unverified_ssl_fallback(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test Zeroconf discovery falls back to unverified SSL if verified SSL fails."""
    mock_indi_allsky_client.fetch_image.side_effect = [
        IndiAllSkyConnectionError("SSL verification failed"),
        b"fake_image",
    ]

    discovery_info = ZeroconfServiceInfo(
        ip_address="192.168.1.50",
        ip_addresses=["192.168.1.50"],
        port=443,
        hostname="indi-allsky.local.",
        type="_indi-allsky._tcp.local.",
        name="INDI Allsky._indi-allsky._tcp.local.",
        properties={"path": "/indi-allsky", "mac": "aa:bb:cc:dd:ee:ff"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "unverified_ssl"
    assert result["description_placeholders"] == {"name": "INDI Allsky"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"
    assert result["data"][CONF_VERIFY_SSL] is False


async def test_zeroconf_requires_auth_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test Zeroconf discovery asks for credentials when device requires authentication."""
    mock_indi_allsky_client.fetch_image.side_effect = IndiAllSkyAuthError(
        "Unauthorized"
    )

    discovery_info = ZeroconfServiceInfo(
        ip_address="192.168.1.50",
        ip_addresses=["192.168.1.50"],
        port=443,
        hostname="indi-allsky.local.",
        type="_indi-allsky._tcp.local.",
        name="INDI Allsky._indi-allsky._tcp.local.",
        properties={"path": "/indi-allsky", "mac": "aa:bb:cc:dd:ee:ff"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert result["description_placeholders"] == {"name": "INDI Allsky"}

    mock_indi_allsky_client.fetch_image.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"
    assert result["title"] == "INDI Allsky (192.168.1.50)"
    assert result["data"] == {
        CONF_HOST: "192.168.1.50",
        CONF_PORT: 443,
        CONF_SSL: True,
        CONF_VERIFY_SSL: True,
        CONF_USERNAME: "test-user",
        CONF_PASSWORD: "test-password",
    }


async def test_zeroconf_credentials_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test error handling when submitting credentials in discovery flow."""
    mock_indi_allsky_client.fetch_image.side_effect = IndiAllSkyAuthError(
        "Unauthorized"
    )

    discovery_info = ZeroconfServiceInfo(
        ip_address="192.168.1.50",
        ip_addresses=["192.168.1.50"],
        port=80,
        hostname="indi-allsky.local.",
        type="_indi-allsky._tcp.local.",
        name="INDI Allsky._indi-allsky._tcp.local.",
        properties={"path": "/indi-allsky", "ssl": "false", "mac": "aa:bb:cc:dd:ee:ff"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "only-user",
            CONF_PASSWORD: "",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert result["errors"] == {"base": "missing_credentials"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "wrong-user",
            CONF_PASSWORD: "wrong-password",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert result["errors"] == {"base": "invalid_auth"}

    mock_indi_allsky_client.fetch_image.side_effect = IndiAllSkyConnectionError(
        "Cannot connect"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "user",
            CONF_PASSWORD: "password",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert result["errors"] == {"base": "cannot_connect"}

    mock_indi_allsky_client.fetch_image.side_effect = RuntimeError("Unexpected failure")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "user",
            CONF_PASSWORD: "password",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert result["errors"] == {"base": "unknown"}

    mock_indi_allsky_client.fetch_image.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "correct-user",
            CONF_PASSWORD: "correct-password",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USERNAME] == "correct-user"
    assert result["data"][CONF_PASSWORD] == "correct-password"
    assert result["data"][CONF_SSL] is False


async def test_zeroconf_cannot_connect_non_ssl(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test Zeroconf discovery aborts immediately if non-SSL connection fails."""
    mock_indi_allsky_client.fetch_image.side_effect = IndiAllSkyConnectionError(
        "Cannot connect"
    )

    discovery_info = ZeroconfServiceInfo(
        ip_address="192.168.1.50",
        ip_addresses=["192.168.1.50"],
        port=80,
        hostname="indi-allsky.local.",
        type="_indi-allsky._tcp.local.",
        name="INDI Allsky._indi-allsky._tcp.local.",
        properties={"path": "/indi-allsky", "ssl": "false", "mac": "aa:bb:cc:dd:ee:ff"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_unverified_ssl_fallback_requires_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test Zeroconf discovery falls back to unverified SSL and requests auth."""
    mock_indi_allsky_client.fetch_image.side_effect = [
        IndiAllSkyConnectionError("SSL verification failed"),
        IndiAllSkyAuthError("Unauthorized"),
    ]

    discovery_info = ZeroconfServiceInfo(
        ip_address="192.168.1.50",
        ip_addresses=["192.168.1.50"],
        port=443,
        hostname="indi-allsky.local.",
        type="_indi-allsky._tcp.local.",
        name="INDI Allsky._indi-allsky._tcp.local.",
        properties={"path": "/indi-allsky", "mac": "aa:bb:cc:dd:ee:ff"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "unverified_ssl"
    assert result["description_placeholders"] == {"name": "INDI Allsky"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"

    mock_indi_allsky_client.fetch_image.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"
    assert result["data"][CONF_VERIFY_SSL] is False
    assert result["data"][CONF_USERNAME] == "test-user"
    assert result["data"][CONF_PASSWORD] == "test-password"


async def test_zeroconf_adopts_existing_unlinked_manual_entry(
    hass: HomeAssistant,
) -> None:
    """Test Zeroconf assigns unique_id to an existing manual entry matching host and port."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=None,
        title="INDI Allsky (192.168.1.50)",
        data={
            CONF_HOST: "192.168.1.50",
            CONF_PORT: 443,
            CONF_SSL: True,
            CONF_VERIFY_SSL: True,
        },
    )
    entry.add_to_hass(hass)

    discovery_info = ZeroconfServiceInfo(
        ip_address="192.168.1.50",
        ip_addresses=["192.168.1.50"],
        port=443,
        hostname="indi-allsky.local.",
        type="_indi-allsky._tcp.local.",
        name="INDI Allsky._indi-allsky._tcp.local.",
        properties={"path": "/indi-allsky", "mac": "aa:bb:cc:dd:ee:ff"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff"


async def test_zeroconf_adopts_existing_unlinked_manual_entry_by_hostname(
    hass: HomeAssistant,
) -> None:
    """Test Zeroconf assigns unique_id to an existing manual entry matching hostname and port."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=None,
        title="INDI Allsky (indi-allsky.local)",
        data={
            CONF_HOST: "indi-allsky.local",
            CONF_PORT: 443,
            CONF_SSL: True,
            CONF_VERIFY_SSL: True,
        },
    )
    entry.add_to_hass(hass)

    discovery_info = ZeroconfServiceInfo(
        ip_address="192.168.1.50",
        ip_addresses=["192.168.1.50"],
        port=443,
        hostname="indi-allsky.local.",
        type="_indi-allsky._tcp.local.",
        name="INDI Allsky._indi-allsky._tcp.local.",
        properties={"path": "/indi-allsky", "mac": "aa:bb:cc:dd:ee:ff"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff"
    assert entry.data[CONF_HOST] == "indi-allsky.local"


async def test_zeroconf_already_configured_with_mac_updates_info(
    hass: HomeAssistant,
) -> None:
    """Test Zeroconf discovery updates entry host/port if unique_id is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
        title="INDI Allsky (192.168.1.20)",
        data={
            CONF_HOST: "192.168.1.20",
            CONF_PORT: 443,
            CONF_SSL: True,
            CONF_VERIFY_SSL: True,
        },
    )
    entry.add_to_hass(hass)

    discovery_info = ZeroconfServiceInfo(
        ip_address="192.168.1.50",
        ip_addresses=["192.168.1.50"],
        port=8443,
        hostname="indi-allsky.local.",
        type="_indi-allsky._tcp.local.",
        name="INDI Allsky._indi-allsky._tcp.local.",
        properties={"path": "/indi-allsky", "mac": "aa:bb:cc:dd:ee:ff"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.168.1.50"
    assert entry.data[CONF_PORT] == 8443


async def test_zeroconf_preserves_configured_hostname(
    hass: HomeAssistant,
) -> None:
    """Test Zeroconf preserves a configured domain hostname when updating an entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
        title="INDI Allsky (allsky.local)",
        data={
            CONF_HOST: "allsky.local",
            CONF_PORT: 443,
            CONF_SSL: True,
            CONF_VERIFY_SSL: True,
        },
    )
    entry.add_to_hass(hass)

    discovery_info = ZeroconfServiceInfo(
        ip_address="192.168.1.50",
        ip_addresses=["192.168.1.50"],
        port=8443,
        hostname="indi-allsky.local.",
        type="_indi-allsky._tcp.local.",
        name="INDI Allsky._indi-allsky._tcp.local.",
        properties={"path": "/indi-allsky", "mac": "aa:bb:cc:dd:ee:ff"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "allsky.local"
    assert entry.data[CONF_PORT] == 8443


async def test_zeroconf_already_configured_without_mac(
    hass: HomeAssistant,
) -> None:
    """Test Zeroconf discovery aborts if host/port match an existing entry when mac is absent."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="INDI Allsky (192.168.1.50)",
        data={
            CONF_HOST: "192.168.1.50",
            CONF_PORT: 443,
            CONF_SSL: True,
            CONF_VERIFY_SSL: True,
        },
    )
    entry.add_to_hass(hass)

    discovery_info = ZeroconfServiceInfo(
        ip_address="192.168.1.50",
        ip_addresses=["192.168.1.50"],
        port=443,
        hostname="indi-allsky.local.",
        type="_indi-allsky._tcp.local.",
        name="INDI Allsky._indi-allsky._tcp.local.",
        properties={"path": "/indi-allsky", "ssl": "true"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_already_configured_without_mac_by_hostname(
    hass: HomeAssistant,
) -> None:
    """Test Zeroconf discovery aborts if hostname/port match an existing entry when mac is absent."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="INDI Allsky (indi-allsky.local)",
        data={
            CONF_HOST: "indi-allsky.local",
            CONF_PORT: 443,
            CONF_SSL: True,
            CONF_VERIFY_SSL: True,
        },
    )
    entry.add_to_hass(hass)

    discovery_info = ZeroconfServiceInfo(
        ip_address="192.168.1.50",
        ip_addresses=["192.168.1.50"],
        port=443,
        hostname="indi-allsky.local.",
        type="_indi-allsky._tcp.local.",
        name="INDI Allsky._indi-allsky._tcp.local.",
        properties={"path": "/indi-allsky", "ssl": "true"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_confirmation_collision_aborts(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test discovery confirmation aborts if endpoint was configured while discovery was pending."""
    discovery_info = ZeroconfServiceInfo(
        ip_address="192.168.1.50",
        ip_addresses=["192.168.1.50"],
        port=443,
        hostname="indi-allsky.local.",
        type="_indi-allsky._tcp.local.",
        name="INDI Allsky._indi-allsky._tcp.local.",
        properties={"path": "/indi-allsky"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    # Add an entry before user clicks submit
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="INDI Allsky (192.168.1.50)",
        data={
            CONF_HOST: "192.168.1.50",
            CONF_PORT: 443,
            CONF_SSL: True,
            CONF_VERIFY_SSL: True,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_rejects_protocol_downgrade(
    hass: HomeAssistant,
) -> None:
    """Test Zeroconf discovery aborts without changing protocol if SSL settings differ."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
        title="INDI Allsky (192.168.1.50)",
        data={
            CONF_HOST: "192.168.1.50",
            CONF_PORT: 443,
            CONF_SSL: True,
            CONF_VERIFY_SSL: True,
        },
    )
    entry.add_to_hass(hass)

    discovery_info = ZeroconfServiceInfo(
        ip_address="192.168.1.50",
        ip_addresses=["192.168.1.50"],
        port=80,
        hostname="indi-allsky.local.",
        type="_indi-allsky._tcp.local.",
        name="INDI Allsky._indi-allsky._tcp.local.",
        properties={"path": "/indi-allsky", "ssl": "false", "mac": "aa:bb:cc:dd:ee:ff"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_PORT] == 443
    assert entry.data[CONF_SSL] is True


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

    with patch(
        "homeassistant.components.indi_allsky.config_flow.IndiAllSkyClient",
        return_value=mock_indi_allsky_client,
    ) as mock_client_cls:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "127.0.0.1",
                CONF_PORT: 443,
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_password",
            },
        )
        mock_client_cls.assert_called_once()
        assert mock_client_cls.call_args.kwargs["username"] == "test_user"
        assert mock_client_cls.call_args.kwargs["password"] == "test_password"

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id is None
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
    assert result["result"].unique_id is None
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 443,
        CONF_SSL: True,
        CONF_VERIFY_SSL: True,
        CONF_USERNAME: "test-user",
        CONF_PASSWORD: "test-password",
    }


@pytest.mark.usefixtures("mock_setup_entry")
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

    with patch(
        "homeassistant.components.indi_allsky.config_flow.IndiAllSkyClient",
        return_value=mock_indi_allsky_client,
    ) as mock_client_cls:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "updated_user",
                CONF_PASSWORD: "updated_password",
            },
        )
        mock_client_cls.assert_called_once()
        assert mock_client_cls.call_args.kwargs["username"] == "updated_user"
        assert mock_client_cls.call_args.kwargs["password"] == "updated_password"

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_USERNAME] == "updated_user"
    assert mock_config_entry.data[CONF_PASSWORD] == "updated_password"


@pytest.mark.usefixtures("mock_setup_entry")
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


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    "credentials_input",
    [
        {CONF_USERNAME: "new_user", CONF_PASSWORD: ""},
        {CONF_USERNAME: "", CONF_PASSWORD: "new_password"},
    ],
)
async def test_reauth_missing_credentials_failure(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    credentials_input: dict[str, str],
) -> None:
    """Test entering empty username or password during reauth yields missing_credentials error."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        credentials_input,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "missing_credentials"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "valid_user",
            CONF_PASSWORD: "valid_password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_USERNAME] == "valid_user"
    assert mock_config_entry.data[CONF_PASSWORD] == "valid_password"

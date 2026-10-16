"""Test the INDI Allsky Config flow."""

import ssl
from unittest.mock import AsyncMock

from aioindiallsky import IndiAllSkyAuthError, IndiAllSkyConnectionError
import pytest

from homeassistant import config_entries
from homeassistant.components.indi_allsky.const import DOMAIN
from homeassistant.components.indi_allsky.util import (
    get_ssl_context,
    is_ip_address,
    normalize_host,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

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


def test_is_ip_address() -> None:
    """Test is_ip_address detection for IPv4, IPv6, and hostnames."""
    assert is_ip_address("127.0.0.1") is True
    assert is_ip_address("192.168.1.1") is True
    assert is_ip_address("::1") is True
    assert is_ip_address("[::1]") is True
    assert is_ip_address("indi-allsky.local") is False
    assert is_ip_address("allsky.domain.com") is False


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
                type="_https._tcp.local.",
                name="INDI Allsky._https._tcp.local.",
                properties={"path": "/indi-allsky", "mac": "AA-BB-CC-DD-EE-FF"},
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
                type="_http._tcp.local.",
                name="INDI Allsky._http._tcp.local.",
                properties={"path": "/indi-allsky"},
            ),
            False,
            80,
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
    mock_setup_entry: AsyncMock,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test Zeroconf discovery offers prefilled user step if connection check fails."""
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Verify user can update settings (e.g. disable verify_ssl) and complete setup
    mock_indi_allsky_client.fetch_image.side_effect = None
    mock_indi_allsky_client.fetch_image.return_value = b"test"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "indi-allsky.local",
            CONF_PORT: 443,
            CONF_SSL: True,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"
    assert result["data"] == {
        CONF_HOST: "indi-allsky.local",
        CONF_PORT: 443,
        CONF_SSL: True,
        CONF_VERIFY_SSL: False,
    }


async def test_zeroconf_unknown_error(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test Zeroconf discovery aborts on unexpected error."""
    mock_indi_allsky_client.fetch_image.side_effect = RuntimeError("Crash")

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
    assert result["reason"] == "unknown"


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
        type="_https._tcp.local.",
        name="INDI Allsky._https._tcp.local.",
        properties={"path": "/indi-allsky"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_already_configured_manual_entry_adopts_mac(
    hass: HomeAssistant,
) -> None:
    """Test Zeroconf discovery adopts MAC unique ID for matching manual entry without unique ID."""
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


async def test_zeroconf_already_configured_manual_entry_with_hostname_adopts_mac_and_preserves_hostname(
    hass: HomeAssistant,
) -> None:
    """Test Zeroconf discovery adopts MAC for hostname-configured entry and preserves the hostname."""
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


async def test_zeroconf_alternate_protocol_announcement_preserves_configured_protocol(
    hass: HomeAssistant,
) -> None:
    """Test alternate HTTP announcement does not overwrite configured HTTPS endpoint."""
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
        type="_http._tcp.local.",
        name="INDI Allsky._http._tcp.local.",
        properties={"path": "/indi-allsky", "mac": "aa:bb:cc:dd:ee:ff"},
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


async def test_zeroconf_skips_adoption_if_mac_already_configured(
    hass: HomeAssistant,
) -> None:
    """Test Zeroconf skips adopting manual entry if an entry with the MAC already exists."""
    existing_mac_entry = MockConfigEntry(
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
    existing_mac_entry.add_to_hass(hass)

    manual_entry = MockConfigEntry(
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
    manual_entry.add_to_hass(hass)

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
    assert existing_mac_entry.unique_id == "aa:bb:cc:dd:ee:ff"
    assert manual_entry.unique_id is None


async def test_zeroconf_already_configured_without_mac_matches_hostname(
    hass: HomeAssistant,
) -> None:
    """Test Zeroconf discovery without MAC aborts if hostname matches an existing entry."""
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
        type="_https._tcp.local.",
        name="INDI Allsky._https._tcp.local.",
        properties={"path": "/indi-allsky"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_rediscovery_ignored_entry_aborts(
    hass: HomeAssistant,
) -> None:
    """Test Zeroconf discovery aborts cleanly when an ignored entry exists for the MAC."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=config_entries.SOURCE_IGNORE,
        unique_id="aa:bb:cc:dd:ee:ff",
        data={},
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


async def test_zeroconf_dual_stack_adopts_matching_ipv4_entry(
    hass: HomeAssistant,
) -> None:
    """Test dual-stack discovery matches and adopts existing IPv4 entry when IPv6 is primary."""
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
        ip_address="2001:db8::1",
        ip_addresses=["2001:db8::1", "192.168.1.50"],
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
    assert entry.data[CONF_HOST] == "192.168.1.50"


async def test_zeroconf_discovery_custom_service_honors_ssl_txt_property(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test custom service type honors ssl=false in TXT record and falls back to port 80."""
    discovery_info = ZeroconfServiceInfo(
        ip_address="192.168.1.50",
        ip_addresses=["192.168.1.50"],
        port=None,
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
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"
    assert result["data"] == {
        CONF_HOST: "192.168.1.50",
        CONF_PORT: 80,
        CONF_SSL: False,
        CONF_VERIFY_SSL: True,
    }


async def test_zeroconf_prevent_duplicate_for_endpoint_configured_during_confirmation(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test duplicate entry is prevented when manual configuration completes while confirmation is pending."""
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
    assert result["step_id"] == "discovery_confirm"

    # User manually configures the same endpoint before confirming discovery
    manual_entry = MockConfigEntry(
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
    manual_entry.add_to_hass(hass)

    # Confirmation step is now submitted
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert manual_entry.unique_id == "aa:bb:cc:dd:ee:ff"


async def test_zeroconf_fallback_step_prevent_duplicate_entry_when_manual_entry_created_with_ip_alias(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test fallback user step prevents duplicate entry if manual entry with IP alias is created while form is open."""
    # First connection check against literal IP fails
    mock_indi_allsky_client.fetch_image.side_effect = IndiAllSkyConnectionError(
        "Certificate verification failed"
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

    # Form falls back to user step prefilled with hostname indi-allsky.local
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # User manually configures entry via literal IP while the fallback form is open
    manual_entry = MockConfigEntry(
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
    manual_entry.add_to_hass(hass)

    # Fallback form is now submitted with hostname indi-allsky.local
    mock_indi_allsky_client.fetch_image.side_effect = None
    mock_indi_allsky_client.fetch_image.return_value = b"test"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "indi-allsky.local",
            CONF_PORT: 443,
            CONF_SSL: True,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert manual_entry.unique_id == "aa:bb:cc:dd:ee:ff"

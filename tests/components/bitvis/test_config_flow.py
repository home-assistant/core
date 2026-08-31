"""Tests for the Bitvis Power Hub config flow."""

import asyncio
from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock, patch

from bitvis_protobuf.parse import PayloadSample
import pytest

from homeassistant.components.bitvis.config_flow import (
    _async_discover_mac_address,
    _async_test_port,
)
from homeassistant.components.bitvis.const import (
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    MODEL_NAME,
)
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import TEST_DEVICE_MAC, patch_config_flow_connectivity

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

ZEROCONF_HOST = "192.168.1.200"
USER_HOST = "192.168.1.100"

ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address(ZEROCONF_HOST),
    ip_addresses=[ip_address(ZEROCONF_HOST)],
    hostname="powerhub.local.",
    name="Bitvis Power Hub._powerhub._udp.local.",
    port=DEFAULT_PORT,
    properties={},
    type="_powerhub._udp.local.",
)


async def test_user_form_create_entry(hass: HomeAssistant) -> None:
    """Test creating an entry via user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch_config_flow_connectivity(USER_HOST):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: USER_HOST,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MODEL_NAME
    assert result["data"] == {
        CONF_HOST: USER_HOST,
        CONF_PORT: DEFAULT_PORT,
    }
    assert result["result"].unique_id == TEST_DEVICE_MAC


async def test_user_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test user form error on port bind failure and recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch_config_flow_connectivity(
        USER_HOST, port_bind_side_effect=OSError("UDP port is unavailable")
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: USER_HOST,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch_config_flow_connectivity(USER_HOST):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: USER_HOST,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MODEL_NAME
    assert result["data"] == {
        CONF_HOST: USER_HOST,
        CONF_PORT: DEFAULT_PORT,
    }
    assert result["result"].unique_id == TEST_DEVICE_MAC


async def test_user_form_discovery_timeout(hass: HomeAssistant) -> None:
    """Test user form error when no UDP message is received in time and recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch_config_flow_connectivity(
        USER_HOST, deliver_mac=False, discovery_timeout=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: USER_HOST,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "timeout_connect"}

    with patch_config_flow_connectivity(USER_HOST):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: USER_HOST,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MODEL_NAME
    assert result["data"] == {
        CONF_HOST: USER_HOST,
        CONF_PORT: DEFAULT_PORT,
    }
    assert result["result"].unique_id == TEST_DEVICE_MAC


async def test_user_form_duplicate(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test duplicate detection by MAC address."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch_config_flow_connectivity(USER_HOST):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: mock_config_entry.data[CONF_HOST],
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_confirm_cannot_connect(hass: HomeAssistant) -> None:
    """Test zeroconf discovery abort on port bind failure."""
    with patch_config_flow_connectivity(
        ZEROCONF_HOST, port_bind_side_effect=OSError("UDP port is unavailable")
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=ZEROCONF_DISCOVERY,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_confirm_discovery_timeout(hass: HomeAssistant) -> None:
    """Test zeroconf discovery abort when no UDP message is received in time."""
    with patch_config_flow_connectivity(
        ZEROCONF_HOST, deliver_mac=False, discovery_timeout=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=ZEROCONF_DISCOVERY,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "timeout_connect"


async def test_zeroconf_duplicate(
    hass: HomeAssistant, mock_zeroconf_config_entry: MockConfigEntry
) -> None:
    """Test that a duplicate zeroconf discovery is aborted."""
    mock_zeroconf_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_none_port_uses_default(hass: HomeAssistant) -> None:
    """Test that a zeroconf discovery with port=None falls back to DEFAULT_PORT."""
    discovery = ZeroconfServiceInfo(
        ip_address=ip_address(ZEROCONF_HOST),
        ip_addresses=[ip_address(ZEROCONF_HOST)],
        hostname="powerhub.local.",
        name="Bitvis Power Hub._powerhub._udp.local.",
        port=None,
        properties={},
        type="_powerhub._udp.local.",
    )

    with patch_config_flow_connectivity(ZEROCONF_HOST):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=discovery,
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PORT] == DEFAULT_PORT


async def test_user_form_create_entry_ipv6_host(hass: HomeAssistant) -> None:
    """Test creating an entry with an IPv6 host via user flow."""
    ipv6_host = "2001:db8::10"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch_config_flow_connectivity(ipv6_host):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: ipv6_host,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MODEL_NAME
    assert result["data"] == {
        CONF_HOST: ipv6_host,
        CONF_PORT: DEFAULT_PORT,
    }
    assert result["result"].unique_id == TEST_DEVICE_MAC


async def test_user_form_duplicate_host(
    hass: HomeAssistant, mock_ipv6_config_entry: MockConfigEntry
) -> None:
    """Test duplicate detection uses the configured host."""
    ipv6_host = mock_ipv6_config_entry.data[CONF_HOST]
    mock_ipv6_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch_config_flow_connectivity(ipv6_host):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: ipv6_host,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_form_keeps_hostname(hass: HomeAssistant) -> None:
    """Test that user flow keeps the configured hostname."""
    hostname = "my-powerhub.local"
    resolved_ip = "10.0.0.5"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch_config_flow_connectivity(resolved_ip):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: hostname,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MODEL_NAME
    assert result["data"][CONF_HOST] == hostname


async def test_user_form_normalize_bracketed_ipv6(hass: HomeAssistant) -> None:
    """Test that bracketed IPv6 host is normalized (brackets stripped)."""
    ipv6_host = "2001:db8::10"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch_config_flow_connectivity(ipv6_host):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: f"[{ipv6_host}]",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MODEL_NAME
    assert result["data"][CONF_HOST] == ipv6_host


async def test_zeroconf_confirm_uses_friendly_name(hass: HomeAssistant) -> None:
    """Test that zeroconf confirm creates entry with friendly name from discovery."""
    discovery = ZeroconfServiceInfo(
        ip_address=ip_address(ZEROCONF_HOST),
        ip_addresses=[ip_address(ZEROCONF_HOST)],
        hostname="powerhub.local.",
        name="My Custom Hub._powerhub._udp.local.",
        port=DEFAULT_PORT,
        properties={},
        type="_powerhub._udp.local.",
    )

    with patch_config_flow_connectivity(ZEROCONF_HOST):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=discovery,
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Custom Hub"


async def test_zeroconf_empty_name_uses_default(hass: HomeAssistant) -> None:
    """Test that zeroconf with empty name falls back to DEFAULT_NAME."""
    discovery = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.201"),
        ip_addresses=[ip_address("192.168.1.201")],
        hostname="powerhub.local.",
        name="",
        port=DEFAULT_PORT,
        properties={},
        type="_powerhub._udp.local.",
    )

    with patch_config_flow_connectivity("192.168.1.201"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=discovery,
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME


async def test_async_test_port_skips_when_listener_exists(
    hass: HomeAssistant,
) -> None:
    """Test _async_test_port returns immediately when a listener already exists."""
    with patch(
        "homeassistant.components.bitvis.config_flow.async_get_listener_registry",
    ) as mock_registry:
        mock_registry.return_value.has_listener.return_value = True
        await _async_test_port(hass, 5000)

    mock_registry.return_value.has_listener.assert_called_once_with(5000)


async def test_async_test_port_binds_and_closes(hass: HomeAssistant) -> None:
    """Test _async_test_port delegates to the library port bind check."""
    with (
        patch(
            "homeassistant.components.bitvis.config_flow.async_get_listener_registry",
        ) as mock_registry,
        patch(
            "homeassistant.components.bitvis.config_flow.async_verify_udp_port_bindable",
            new_callable=AsyncMock,
        ) as mock_verify,
    ):
        mock_registry.return_value.has_listener.return_value = False
        await _async_test_port(hass, 5000)

    mock_verify.assert_awaited_once_with(5000)


async def test_async_test_port_raises_when_all_binds_fail(
    hass: HomeAssistant,
) -> None:
    """Test _async_test_port raises OSError when the library port bind check fails."""
    with (
        patch(
            "homeassistant.components.bitvis.config_flow.async_get_listener_registry",
        ) as mock_registry,
        patch(
            "homeassistant.components.bitvis.config_flow.async_verify_udp_port_bindable",
            new_callable=AsyncMock,
            side_effect=OSError("UDP port is unavailable"),
        ),
    ):
        mock_registry.return_value.has_listener.return_value = False
        with pytest.raises(OSError, match="UDP port is unavailable"):
            await _async_test_port(hass, 5000)


async def test_async_discover_mac_address(hass: HomeAssistant) -> None:
    """Test _async_discover_mac_address registers IP filters and returns MAC."""
    mock_listener = MagicMock()
    mock_listener.register = MagicMock()
    mock_listener.unregister = MagicMock()

    with (
        patch(
            "homeassistant.components.bitvis.config_flow.async_resolve_host",
            new_callable=AsyncMock,
            return_value={USER_HOST},
        ),
        patch(
            "homeassistant.components.bitvis.config_flow.async_get_listener_registry",
        ) as mock_registry,
    ):
        mock_registry.return_value.async_get_or_create = AsyncMock(
            return_value=mock_listener
        )

        discover_task = asyncio.create_task(
            _async_discover_mac_address(hass, USER_HOST, DEFAULT_PORT)
        )
        await hass.async_block_till_done()

        callback = mock_listener.register.call_args[0][1]

        payload = PayloadSample(mac_address=TEST_DEVICE_MAC, sample=MagicMock())
        callback(payload, (USER_HOST, 1234))

        mac_address = await discover_task

    assert mac_address == TEST_DEVICE_MAC
    mock_listener.unregister.assert_called_once()

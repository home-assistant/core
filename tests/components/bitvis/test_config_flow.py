"""Tests for the Bitvis Power Hub config flow."""

import asyncio
from ipaddress import ip_address
import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.bitvis.config_flow import _async_test_port
from homeassistant.components.bitvis.const import DEFAULT_NAME, DEFAULT_PORT, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.1.200"),
    ip_addresses=[ip_address("192.168.1.200")],
    hostname="powerhub.local.",
    name="Bitvis Power Hub._powerhub._udp.local.",
    port=DEFAULT_PORT,
    properties={},
    type="_powerhub._udp.local.",
)


async def test_user_form(hass: HomeAssistant) -> None:
    """Test we get the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_form_create_entry(hass: HomeAssistant) -> None:
    """Test creating an entry via user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.bitvis.config_flow._async_test_port",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.bitvis.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 5000,
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 5000,
    }


async def test_user_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test that a port binding failure surfaces a cannot_connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.bitvis.config_flow._async_test_port",
        side_effect=OSError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 5000,
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_form_duplicate(hass: HomeAssistant) -> None:
    """Test duplicate detection."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 5000,
        },
        unique_id="192.168.1.100:5000",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.bitvis.config_flow._async_test_port",
        new_callable=AsyncMock,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 5000,
            },
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_shows_confirm_form(hass: HomeAssistant) -> None:
    """Test that zeroconf discovery shows the confirmation form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"


async def test_zeroconf_confirm_creates_entry(hass: HomeAssistant) -> None:
    """Test that confirming a zeroconf discovery creates a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    assert result["step_id"] == "zeroconf_confirm"

    with (
        patch(
            "homeassistant.components.bitvis.config_flow._async_test_port",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.bitvis.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "192.168.1.200",
        CONF_PORT: DEFAULT_PORT,
    }


async def test_zeroconf_confirm_cannot_connect(hass: HomeAssistant) -> None:
    """Test that a port bind failure during zeroconf confirm aborts the flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    with patch(
        "homeassistant.components.bitvis.config_flow._async_test_port",
        side_effect=OSError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_duplicate(hass: HomeAssistant) -> None:
    """Test that a duplicate zeroconf discovery is aborted."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.200", CONF_PORT: DEFAULT_PORT},
        unique_id=f"192.168.1.200:{DEFAULT_PORT}",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_none_port_uses_default(hass: HomeAssistant) -> None:
    """Test that a zeroconf discovery with port=None falls back to DEFAULT_PORT."""
    discovery = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.200"),
        ip_addresses=[ip_address("192.168.1.200")],
        hostname="powerhub.local.",
        name="Bitvis Power Hub._powerhub._udp.local.",
        port=None,
        properties={},
        type="_powerhub._udp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery,
    )

    with (
        patch(
            "homeassistant.components.bitvis.config_flow._async_test_port",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.bitvis.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PORT] == DEFAULT_PORT


async def test_user_form_create_entry_ipv6_host(hass: HomeAssistant) -> None:
    """Test creating an entry with an IPv6 host via user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.bitvis.config_flow._async_test_port",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.bitvis.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "2001:db8::10",
                CONF_PORT: 5000,
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "2001:db8::10",
        CONF_PORT: 5000,
    }
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert (
        hass.config_entries.async_entries(DOMAIN)[0].unique_id == "[2001:db8::10]:5000"
    )


async def test_user_form_duplicate_ipv6_bracketed_unique_id(
    hass: HomeAssistant,
) -> None:
    """Test duplicate detection for IPv6 hosts with bracketed unique IDs."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "2001:db8::10",
            CONF_PORT: 5000,
        },
        unique_id="[2001:db8::10]:5000",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.bitvis.config_flow._async_test_port",
        new_callable=AsyncMock,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "2001:db8::10",
                CONF_PORT: 5000,
            },
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_form_resolve_host_gaierror_fallback(
    hass: HomeAssistant,
) -> None:
    """Test that user flow falls back to raw host when DNS resolution fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.bitvis.config_flow._async_test_port",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.bitvis.config_flow._resolve_host",
            side_effect=socket.gaierror,
        ),
        patch(
            "homeassistant.components.bitvis.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "my-powerhub.local",
                CONF_PORT: 5000,
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "my-powerhub.local"


async def test_user_form_normalize_bracketed_ipv6(
    hass: HomeAssistant,
) -> None:
    """Test that bracketed IPv6 host is normalized (brackets stripped)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.bitvis.config_flow._async_test_port",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.bitvis.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "[2001:db8::10]",
                CONF_PORT: 5000,
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "2001:db8::10"


async def test_zeroconf_resolve_host_gaierror_fallback(
    hass: HomeAssistant,
) -> None:
    """Test that zeroconf flow falls back to raw host when DNS resolution fails."""
    with patch(
        "homeassistant.components.bitvis.config_flow._resolve_host",
        side_effect=socket.gaierror,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=ZEROCONF_DISCOVERY,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"


async def test_zeroconf_confirm_uses_friendly_name(hass: HomeAssistant) -> None:
    """Test that zeroconf confirm creates entry with friendly name from discovery."""
    discovery = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.200"),
        ip_addresses=[ip_address("192.168.1.200")],
        hostname="powerhub.local.",
        name="My Custom Hub._powerhub._udp.local.",
        port=DEFAULT_PORT,
        properties={},
        type="_powerhub._udp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery,
    )

    with (
        patch(
            "homeassistant.components.bitvis.config_flow._async_test_port",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.bitvis.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
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

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery,
    )

    with (
        patch(
            "homeassistant.components.bitvis.config_flow._async_test_port",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.bitvis.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME


async def test_async_test_port_skips_when_listener_exists(
    hass: HomeAssistant,
) -> None:
    """Test _async_test_port returns immediately when a listener already exists."""
    with patch(
        "homeassistant.components.bitvis.config_flow.async_get_listener_registry",
    ) as mock_registry:
        mock_registry.return_value.has_listener.return_value = True
        # Should return without attempting to bind
        await _async_test_port(hass, 5000)

    mock_registry.return_value.has_listener.assert_called_once_with(5000)


async def test_async_test_port_binds_and_closes(hass: HomeAssistant) -> None:
    """Test _async_test_port binds transports and closes them."""
    mock_transport = MagicMock(spec=asyncio.DatagramTransport)

    with (
        patch(
            "homeassistant.components.bitvis.config_flow.async_get_listener_registry",
        ) as mock_registry,
        patch.object(
            asyncio.get_running_loop(),
            "create_datagram_endpoint",
            new_callable=AsyncMock,
            return_value=(mock_transport, MagicMock()),
        ),
    ):
        mock_registry.return_value.has_listener.return_value = False
        await _async_test_port(hass, 5000)

    mock_transport.close.assert_called()


async def test_async_test_port_raises_when_all_binds_fail(
    hass: HomeAssistant,
) -> None:
    """Test _async_test_port raises OSError when no binds succeed."""
    with patch(
        "homeassistant.components.bitvis.config_flow.async_get_listener_registry",
    ) as mock_registry:
        mock_registry.return_value.has_listener.return_value = False
        with (
            patch.object(
                asyncio.get_running_loop(),
                "create_datagram_endpoint",
                new_callable=AsyncMock,
                side_effect=OSError("bind failed"),
            ),
            pytest.raises(OSError, match="UDP port is unavailable"),
        ):
            await _async_test_port(hass, 5000)

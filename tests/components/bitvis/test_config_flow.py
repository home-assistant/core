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

from .conftest import TEST_DEVICE_MAC

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
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_form_create_entry(hass: HomeAssistant) -> None:
    """Test creating an entry via user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.bitvis.config_flow._async_test_port",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.bitvis.config_flow._async_discover_mac_address",
            new_callable=AsyncMock,
            return_value=TEST_DEVICE_MAC,
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
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == MODEL_NAME
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: DEFAULT_PORT,
    }
    assert hass.config_entries.async_entries(DOMAIN)[0].unique_id == TEST_DEVICE_MAC


@pytest.mark.parametrize("recover", [False, True])
async def test_user_form_cannot_connect(hass: HomeAssistant, recover: bool) -> None:
    """Test user form error on port bind failure, optionally with recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.bitvis.config_flow._async_test_port",
        side_effect=OSError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    if recover:
        with (
            patch(
                "homeassistant.components.bitvis.config_flow._async_test_port",
                new_callable=AsyncMock,
            ),
            patch(
                "homeassistant.components.bitvis.config_flow._async_discover_mac_address",
                new_callable=AsyncMock,
                return_value=TEST_DEVICE_MAC,
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
                },
            )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == MODEL_NAME
        assert result["data"] == {
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
        }


async def test_user_form_discovery_timeout(hass: HomeAssistant) -> None:
    """Test user form error when no UDP message is received in time."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.bitvis.config_flow._async_test_port",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.bitvis.config_flow._async_discover_mac_address",
            side_effect=TimeoutError,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "timeout_connect"}


async def test_user_form_duplicate(hass: HomeAssistant) -> None:
    """Test duplicate detection by MAC address."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
        },
        unique_id=TEST_DEVICE_MAC,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.bitvis.config_flow._async_test_port",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.bitvis.config_flow._async_discover_mac_address",
            new_callable=AsyncMock,
            return_value=TEST_DEVICE_MAC,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
            },
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_confirm_creates_entry(hass: HomeAssistant) -> None:
    """Test that zeroconf discovery shows confirmation form and creates entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    with (
        patch(
            "homeassistant.components.bitvis.config_flow._async_test_port",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.bitvis.config_flow._async_discover_mac_address",
            new_callable=AsyncMock,
            return_value=TEST_DEVICE_MAC,
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
    assert hass.config_entries.async_entries(DOMAIN)[0].unique_id == TEST_DEVICE_MAC


@pytest.mark.parametrize("recover", [False, True])
async def test_zeroconf_confirm_cannot_connect(
    hass: HomeAssistant, recover: bool
) -> None:
    """Test zeroconf confirm abort on port bind failure, optionally with recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
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

    if recover:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=ZEROCONF_DISCOVERY,
        )

        with (
            patch(
                "homeassistant.components.bitvis.config_flow._async_test_port",
                new_callable=AsyncMock,
            ),
            patch(
                "homeassistant.components.bitvis.config_flow._async_discover_mac_address",
                new_callable=AsyncMock,
                return_value=TEST_DEVICE_MAC,
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


async def test_zeroconf_confirm_discovery_timeout(hass: HomeAssistant) -> None:
    """Test zeroconf confirm abort when no UDP message is received in time."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    with (
        patch(
            "homeassistant.components.bitvis.config_flow._async_test_port",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.bitvis.config_flow._async_discover_mac_address",
            side_effect=TimeoutError,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "timeout_connect"


async def test_zeroconf_duplicate(hass: HomeAssistant) -> None:
    """Test that a duplicate zeroconf discovery is aborted."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.200", CONF_PORT: DEFAULT_PORT},
        unique_id=TEST_DEVICE_MAC,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
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
        context={"source": SOURCE_ZEROCONF},
        data=discovery,
    )

    with (
        patch(
            "homeassistant.components.bitvis.config_flow._async_test_port",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.bitvis.config_flow._async_discover_mac_address",
            new_callable=AsyncMock,
            return_value=TEST_DEVICE_MAC,
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
        DOMAIN, context={"source": SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.bitvis.config_flow._async_test_port",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.bitvis.config_flow._async_discover_mac_address",
            new_callable=AsyncMock,
            return_value=TEST_DEVICE_MAC,
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
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == MODEL_NAME
    assert result["data"] == {
        CONF_HOST: "2001:db8::10",
        CONF_PORT: DEFAULT_PORT,
    }
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert hass.config_entries.async_entries(DOMAIN)[0].unique_id == TEST_DEVICE_MAC


async def test_user_form_duplicate_host(hass: HomeAssistant) -> None:
    """Test duplicate detection uses the configured host."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "2001:db8::10",
            CONF_PORT: DEFAULT_PORT,
        },
        unique_id="11:22:33:44:55:66",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.bitvis.config_flow._async_test_port",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.bitvis.config_flow._async_discover_mac_address",
            new_callable=AsyncMock,
            return_value=TEST_DEVICE_MAC,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "2001:db8::10",
            },
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_form_keeps_hostname(
    hass: HomeAssistant,
) -> None:
    """Test that user flow keeps the configured hostname."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.bitvis.config_flow._async_test_port",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.bitvis.config_flow._async_discover_mac_address",
            new_callable=AsyncMock,
            return_value=TEST_DEVICE_MAC,
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
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == MODEL_NAME
    assert result["data"][CONF_HOST] == "my-powerhub.local"


async def test_user_form_normalize_bracketed_ipv6(
    hass: HomeAssistant,
) -> None:
    """Test that bracketed IPv6 host is normalized (brackets stripped)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.bitvis.config_flow._async_test_port",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.bitvis.config_flow._async_discover_mac_address",
            new_callable=AsyncMock,
            return_value=TEST_DEVICE_MAC,
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
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == MODEL_NAME
    assert result["data"][CONF_HOST] == "2001:db8::10"


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
        context={"source": SOURCE_ZEROCONF},
        data=discovery,
    )

    with (
        patch(
            "homeassistant.components.bitvis.config_flow._async_test_port",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.bitvis.config_flow._async_discover_mac_address",
            new_callable=AsyncMock,
            return_value=TEST_DEVICE_MAC,
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
        context={"source": SOURCE_ZEROCONF},
        data=discovery,
    )

    with (
        patch(
            "homeassistant.components.bitvis.config_flow._async_test_port",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.bitvis.config_flow._async_discover_mac_address",
            new_callable=AsyncMock,
            return_value=TEST_DEVICE_MAC,
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
            hass.loop,
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
                hass.loop,
                "create_datagram_endpoint",
                new_callable=AsyncMock,
                side_effect=OSError("bind failed"),
            ),
            pytest.raises(OSError, match="UDP port is unavailable"),
        ):
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
            return_value={"192.168.1.100"},
        ),
        patch(
            "homeassistant.components.bitvis.config_flow.async_get_listener_registry",
        ) as mock_registry,
    ):
        mock_registry.return_value.async_get_or_create = AsyncMock(
            return_value=mock_listener
        )

        discover_task = asyncio.create_task(
            _async_discover_mac_address(hass, "192.168.1.100", DEFAULT_PORT)
        )
        await hass.async_block_till_done()

        callback = mock_listener.register.call_args[0][1]

        payload = PayloadSample(mac_address=TEST_DEVICE_MAC, sample=MagicMock())
        callback(payload, ("192.168.1.100", 1234))

        mac_address = await discover_task

    assert mac_address == TEST_DEVICE_MAC
    mock_listener.unregister.assert_called_once()

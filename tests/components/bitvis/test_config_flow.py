"""Tests for the Bitvis Power Hub config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
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

"""Tests for the LinkPlay config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock

from homeassistant.components.linkplay import DOMAIN
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import HOST, HOST_REENTRY, NAME, UUID

ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address(HOST),
    ip_addresses=[ip_address(HOST)],
    hostname=f"{NAME}.local.",
    name=f"{NAME}._linkplay._tcp.local.",
    port=59152,
    type="_linkplay._tcp.local.",
    properties={
        "uuid": f"uuid:{UUID}",
        "mac": "00:2F:69:01:84:3A",
        "security": "https 2.0",
        "upnp": "1.0.0",
        "bootid": "1f347886-1dd2-11b2-86ab-aa0cd2803583",
    },
)

ZEROCONF_DISCOVERY_RE_ENTRY = ZeroconfServiceInfo(
    ip_address=ip_address(HOST_REENTRY),
    ip_addresses=[ip_address(HOST_REENTRY)],
    hostname=f"{NAME}.local.",
    name=f"{NAME}._linkplay._tcp.local.",
    port=59152,
    type="_linkplay._tcp.local.",
    properties={
        "uuid": f"uuid:{UUID}",
        "mac": "00:2F:69:01:84:3A",
        "security": "https 2.0",
        "upnp": "1.0.0",
        "bootid": "1f347886-1dd2-11b2-86ab-aa0cd2803583",
    },
)


async def test_user_flow(
    hass: HomeAssistant,
    mock_linkplay_factory_bridge: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user setup config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Smart Zone 1_54B9"
    assert result["data"] == {
        CONF_HOST: HOST,
    }
    assert result["result"].unique_id == "FF31F09E-5001-FBDE-0546-2DBFFF31F09E"


async def test_user_flow_re_entry(
    hass: HomeAssistant,
    mock_linkplay_factory_bridge: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user setup config flow."""

    # Create initial entry
    await test_user_flow(hass, mock_linkplay_factory_bridge, mock_setup_entry)

    # Re-create entry with different host
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.22"},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_flow(
    hass: HomeAssistant,
    mock_linkplay_factory_bridge: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test Zeroconf flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Smart Zone 1_54B9"
    assert result["data"] == {
        CONF_HOST: HOST,
    }
    assert result["result"].unique_id == "FF31F09E-5001-FBDE-0546-2DBFFF31F09E"


async def test_zeroconf_flow_re_entry(
    hass: HomeAssistant,
    mock_linkplay_factory_bridge: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test Zeroconf flow."""

    # Create initial entry
    await test_zeroconf_flow(hass, mock_linkplay_factory_bridge, mock_setup_entry)

    # Re-create entry with different host
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY_RE_ENTRY,
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_errors(
    hass: HomeAssistant,
    mock_linkplay_factory_bridge_empty: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test flow errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

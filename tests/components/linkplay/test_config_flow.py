"""Tests for the LinkPlay config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock

from linkplay.exceptions import LinkPlayRequestException
import pytest

from homeassistant.components.linkplay.const import DOMAIN
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import HOST, HOST_REENTRY, NAME, UUID

from tests.common import MockConfigEntry

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


@pytest.mark.usefixtures("mock_linkplay_factory_bridge", "mock_setup_entry")
async def test_user_flow(
    hass: HomeAssistant,
) -> None:
    """Test user setup config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {
        CONF_HOST: HOST,
    }
    assert result["result"].unique_id == UUID


@pytest.mark.usefixtures("mock_linkplay_factory_bridge")
async def test_user_flow_re_entry(
    hass: HomeAssistant,
) -> None:
    """Test user setup config flow when an entry with the same unique id already exists."""

    # Create mock entry which already has the same UUID
    entry = MockConfigEntry(
        data={CONF_HOST: HOST},
        domain=DOMAIN,
        title=NAME,
        unique_id=UUID,
    )
    entry.add_to_hass(hass)

    # Re-create entry with different host
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST_REENTRY},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_linkplay_factory_bridge", "mock_setup_entry")
async def test_zeroconf_flow(
    hass: HomeAssistant,
) -> None:
    """Test Zeroconf flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {
        CONF_HOST: HOST,
    }
    assert result["result"].unique_id == UUID


@pytest.mark.usefixtures("mock_linkplay_factory_bridge")
async def test_zeroconf_flow_re_entry(
    hass: HomeAssistant,
) -> None:
    """Test Zeroconf flow when an entry with the same unique id already exists."""

    # Create mock entry which already has the same UUID
    entry = MockConfigEntry(
        data={CONF_HOST: HOST},
        domain=DOMAIN,
        title=NAME,
        unique_id=UUID,
    )
    entry.add_to_hass(hass)

    # Re-create entry with different host
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY_RE_ENTRY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow_errors(
    hass: HomeAssistant,
    mock_linkplay_factory_bridge: AsyncMock,
) -> None:
    """Test flow when the device discovered through Zeroconf cannot be reached."""

    # Temporarily make the mock_linkplay_factory_bridge throw an exception
    mock_linkplay_factory_bridge.side_effect = (LinkPlayRequestException("Error"),)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_linkplay_factory_bridge: AsyncMock,
) -> None:
    """Test flow when the device cannot be reached."""

    # Temporarily make the mock_linkplay_factory_bridge throw an exception
    mock_linkplay_factory_bridge.side_effect = (LinkPlayRequestException("Error"),)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    # Make mock_linkplay_factory_bridge_exception no longer throw an exception
    mock_linkplay_factory_bridge.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {
        CONF_HOST: HOST,
    }
    assert result["result"].unique_id == UUID

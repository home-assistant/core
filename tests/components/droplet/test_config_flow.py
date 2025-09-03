"""Test Droplet config flow."""

from ipaddress import IPv4Address
from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_CODE, CONF_DEVICE_ID, CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import MOCK_CODE, MOCK_DEVICE_ID, MOCK_HOST, MOCK_PORT

from tests.common import MockConfigEntry


async def test_user_setup(
    hass: HomeAssistant,
    mock_droplet_discovery: AsyncMock,
    mock_droplet_connection: AsyncMock,
    mock_droplet: AsyncMock,
) -> None:
    """Test successful Droplet user setup."""
    result = await hass.config_entries.flow.async_init(
        "droplet", context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        user_input={CONF_CODE: MOCK_CODE, CONF_IP_ADDRESS: "192.168.1.2"},
    )
    assert result is not None
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("data") == {
        CONF_CODE: MOCK_CODE,
        CONF_DEVICE_ID: MOCK_DEVICE_ID,
        CONF_IP_ADDRESS: MOCK_HOST,
        CONF_PORT: MOCK_PORT,
    }
    assert result.get("context") is not None
    assert result.get("context", {}).get("unique_id") == MOCK_DEVICE_ID


@pytest.mark.parametrize(
    ("device_id", "connect_res"),
    [
        (
            "",
            True,
        ),
        (MOCK_DEVICE_ID, False),
    ],
    ids=["no_device_id", "cannot_connect"],
)
async def test_user_setup_fail(
    hass: HomeAssistant,
    device_id,
    connect_res,
    mock_droplet_discovery,
    mock_droplet_connection,
    mock_droplet,
) -> None:
    """Test user setup failing due to no device ID or failed connection."""
    result = await hass.config_entries.flow.async_init(
        "droplet", context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    attrs = {
        "get_device_id.return_value": device_id,
        "try_connect.return_value": connect_res,
    }
    mock_droplet_discovery.configure_mock(**attrs)

    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        user_input={CONF_CODE: MOCK_CODE, CONF_IP_ADDRESS: MOCK_HOST},
    )
    assert result is not None
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "cannot_connect"}

    # The user should be able to try again. Maybe the droplet was disconnected from the network or something
    attrs = {
        "get_device_id.return_value": MOCK_DEVICE_ID,
        "try_connect.return_value": True,
    }
    mock_droplet_discovery.configure_mock(**attrs)
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        user_input={CONF_CODE: MOCK_CODE, CONF_IP_ADDRESS: MOCK_HOST},
    )
    assert result is not None
    assert result.get("type") is FlowResultType.CREATE_ENTRY


async def test_user_setup_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_droplet_discovery,
    mock_droplet,
    mock_droplet_connection,
) -> None:
    """Test user setup of an already-configured device."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "droplet", context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        user_input={CONF_CODE: MOCK_CODE, CONF_IP_ADDRESS: MOCK_HOST},
    )
    assert result is not None
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_zeroconf_setup(
    hass: HomeAssistant,
    mock_droplet_discovery: AsyncMock,
    mock_droplet: AsyncMock,
    mock_droplet_connection: AsyncMock,
) -> None:
    """Test successful setup of Droplet via zeroconf."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=IPv4Address(MOCK_HOST),
        ip_addresses=[IPv4Address(MOCK_HOST)],
        port=MOCK_PORT,
        hostname=MOCK_DEVICE_ID,
        type="_droplet._tcp.local.",
        name=MOCK_DEVICE_ID,
        properties={},
    )
    result = await hass.config_entries.flow.async_init(
        "droplet",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result is not None
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"), user_input={CONF_CODE: MOCK_CODE}
    )
    await hass.async_block_till_done()
    assert result is not None
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("data") == {
        CONF_DEVICE_ID: MOCK_DEVICE_ID,
        CONF_IP_ADDRESS: MOCK_HOST,
        CONF_PORT: MOCK_PORT,
        CONF_CODE: MOCK_CODE,
    }
    assert result.get("context") is not None
    assert result.get("context", {}).get("unique_id") == MOCK_DEVICE_ID


@pytest.mark.parametrize("mock_droplet_discovery", ["192.168.1.5"], indirect=True)
async def test_zeroconf_update(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_droplet_discovery
) -> None:
    """Test updating Droplet's host with zeroconf."""
    mock_config_entry.add_to_hass(hass)

    # We start with a different host
    new_host = "192.168.1.5"
    entries = hass.config_entries.async_entries("droplet")
    assert entries[0].data.get(CONF_IP_ADDRESS) != new_host

    # After this discovery message, host should be updated
    discovery_info = ZeroconfServiceInfo(
        ip_address=IPv4Address(new_host),
        ip_addresses=[IPv4Address(new_host)],
        port=MOCK_PORT,
        hostname=MOCK_DEVICE_ID,
        type="_droplet._tcp.local.",
        name=MOCK_DEVICE_ID,
        properties={},
    )

    result = await hass.config_entries.flow.async_init(
        "droplet",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result is not None
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"

    entries = hass.config_entries.async_entries("droplet")
    assert entries[0].data.get(CONF_IP_ADDRESS) == new_host


async def test_zeroconf_invalid_discovery(hass: HomeAssistant) -> None:
    """Test that invalid discovery information causes the config flow to abort."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=IPv4Address(MOCK_HOST),
        ip_addresses=[IPv4Address(MOCK_HOST)],
        port=-1,
        hostname=MOCK_DEVICE_ID,
        type="_droplet._tcp.local.",
        name=MOCK_DEVICE_ID,
        properties={},
    )
    result = await hass.config_entries.flow.async_init(
        "droplet",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result is not None
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "invalid_discovery_info"


async def test_confirm_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_droplet: AsyncMock,
    mock_droplet_connection: AsyncMock,
    mock_droplet_discovery: AsyncMock,
) -> None:
    """Test that config flow fails when Droplet can't connect."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=IPv4Address(MOCK_HOST),
        ip_addresses=[IPv4Address(MOCK_HOST)],
        port=MOCK_PORT,
        hostname=MOCK_DEVICE_ID,
        type="_droplet._tcp.local.",
        name=MOCK_DEVICE_ID,
        properties={},
    )
    result = await hass.config_entries.flow.async_init(
        "droplet",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result.get("type") == FlowResultType.FORM

    # Mock the connection failing
    mock_droplet_discovery.try_connect.return_value = False

    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"), user_input={"code": MOCK_CODE}
    )
    await hass.async_block_till_done()
    assert result is not None
    assert result.get("type") == FlowResultType.FORM
    errors = result.get("errors")
    assert errors
    assert errors.get("base") == "cannot_connect"

"""Tests for the Knocki event platform."""

from unittest.mock import AsyncMock

from knocki import KnockiConnectionError, KnockiInvalidAuthError
import pytest

from homeassistant.components.knocki.const import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from . import setup_integration

from tests.common import MockConfigEntry

DHCP_DISCOVERY = DhcpServiceInfo(
    ip="1.1.1.1",
    hostname="KNC1-W-00000214",
    macaddress="aa:bb:cc:dd:ee:ff",
)


async def test_full_flow(
    hass: HomeAssistant,
    mock_knocki_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == {
        CONF_TOKEN: "test-token",
    }
    assert result["result"].unique_id == "test-id"
    assert len(mock_knocki_client.link.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplcate_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_knocki_client: AsyncMock,
) -> None:
    """Test abort when setting up duplicate entry."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(("field"), ["login", "link"])
@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (KnockiConnectionError, "cannot_connect"),
        (KnockiInvalidAuthError, "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_exceptions(
    hass: HomeAssistant,
    mock_knocki_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    field: str,
    exception: Exception,
    error: str,
) -> None:
    """Test exceptions."""
    getattr(mock_knocki_client, field).side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    getattr(mock_knocki_client, field).side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_dhcp(
    hass: HomeAssistant,
    mock_knocki_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test DHCP discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_DISCOVERY
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "test-id"


async def test_dhcp_mac(
    hass: HomeAssistant,
    mock_knocki_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test updating the mac address in the DHCP discovery."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(identifiers={(DOMAIN, "KNC1-W-00000214")})
    assert device
    assert device.connections == set()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_DISCOVERY
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    device = device_registry.async_get_device(identifiers={(DOMAIN, "KNC1-W-00000214")})
    assert device
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")}


async def test_dhcp_already_setup(
    hass: HomeAssistant,
    mock_knocki_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test DHCP discovery with already setup device."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_DISCOVERY
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

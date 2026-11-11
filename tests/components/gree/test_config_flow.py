"""Tests for Gree setup and shared DHCP discovery."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.gree.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .common import FakeDiscovery

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@patch("homeassistant.components.gree.config_flow.DISCOVERY_TIMEOUT", 0)
async def test_creating_entry_sets_up_climate(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test setting up Gree creates the climate components."""
    with patch(
        "homeassistant.components.gree.config_flow.Discovery",
        return_value=FakeDiscovery(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY

        await hass.async_block_till_done()

        assert len(mock_setup_entry.mock_calls) == 1


@patch("homeassistant.components.gree.config_flow.DISCOVERY_TIMEOUT", 0)
async def test_creating_entry_has_no_devices(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test setting up Gree creates the climate components."""
    with patch(
        "homeassistant.components.gree.config_flow.Discovery",
        return_value=FakeDiscovery(),
    ) as discovery:
        discovery.return_value.mock_devices = []

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.ABORT

        await hass.async_block_till_done()

        assert len(mock_setup_entry.mock_calls) == 0


async def test_dhcp_discovery(hass: HomeAssistant) -> None:
    """Test DHCP discovery requires confirmation and creates one shared entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(ip="192.168.1.10", hostname="", macaddress="f4911e7aca59"),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert not hass.config_entries.async_entries(DOMAIN)

    duplicate = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(ip="192.168.1.11", hostname="", macaddress="502cc6123456"),
    )
    assert duplicate["type"] is FlowResultType.ABORT
    assert duplicate["reason"] == "single_instance_allowed"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Gree Climate"
    assert result["data"] == {}
    assert result["result"].unique_id == DOMAIN


async def test_dhcp_already_configured(hass: HomeAssistant) -> None:
    """Test DHCP discovery does not duplicate an existing shared entry."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(ip="192.168.1.10", hostname="", macaddress="f4911e7aca59"),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"

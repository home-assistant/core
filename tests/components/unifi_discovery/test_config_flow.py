"""Test the UniFi Discovery config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.unifi_discovery.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from . import DEVICE_HOSTNAME, DEVICE_IP_ADDRESS, DEVICE_MAC_ADDRESS, _patch_discovery

DHCP_DISCOVERY = DhcpServiceInfo(
    hostname=DEVICE_HOSTNAME,
    ip=DEVICE_IP_ADDRESS,
    macaddress=DEVICE_MAC_ADDRESS.lower().replace(":", ""),
)

SSDP_DISCOVERY = SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="mock_st",
    upnp={
        "manufacturer": "Ubiquiti Networks",
        "modelDescription": "UniFi Dream Machine",
    },
)


@pytest.mark.parametrize(
    ("source", "data"),
    [
        (config_entries.SOURCE_DHCP, DHCP_DISCOVERY),
        (config_entries.SOURCE_SSDP, SSDP_DISCOVERY),
    ],
)
async def test_dhcp_ssdp_abort_with_discovery_started(
    hass: HomeAssistant, source: str, data: DhcpServiceInfo | SsdpServiceInfo
) -> None:
    """Test DHCP and SSDP discovery triggers scanner and aborts."""
    with _patch_discovery() as mock_scanner:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source},
            data=data,
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_started"
    assert mock_scanner.async_scan.call_count == 1


@pytest.mark.parametrize(
    ("source", "data"),
    [
        (config_entries.SOURCE_DHCP, DHCP_DISCOVERY),
        (config_entries.SOURCE_SSDP, SSDP_DISCOVERY),
    ],
)
async def test_dhcp_ssdp_abort_already_in_progress(
    hass: HomeAssistant, source: str, data: DhcpServiceInfo | SsdpServiceInfo
) -> None:
    """Test DHCP and SSDP abort when another flow is already in progress."""
    with (
        _patch_discovery(),
        patch(
            "homeassistant.components.unifi_discovery.config_flow.UnifiDiscoveryFlowHandler._async_in_progress",
            return_value=[{"flow_id": "mock_flow"}],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source},
            data=data,
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_user_flow_aborts(hass: HomeAssistant) -> None:
    """Test user-initiated flow aborts."""
    with _patch_discovery() as mock_scanner:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_started"
    assert mock_scanner.async_scan.call_count == 1

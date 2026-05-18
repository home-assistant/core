"""Tests for SSDP config flow steps (flow handler only, no integration setup)."""

from unittest.mock import AsyncMock, patch

import pytest
from custom_components.fritzbox_vpn.config_flow import ConfigFlow
from custom_components.fritzbox_vpn.const import DOMAIN
from homeassistant.config_entries import SOURCE_SSDP
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

MOCK_DEVICE_UUID = "2f402f80-da79-4e15-8e7b-4b6b6b6b6b6b"
MOCK_UDN = f"uuid:{MOCK_DEVICE_UUID}"
MOCK_USN = f"uuid:{MOCK_DEVICE_UUID}::upnp:rootdevice"
MOCK_HOST = "192.168.178.1"


def _router_discovery(**kwargs: object) -> SsdpServiceInfo:
    defaults: dict = {
        "ssdp_st": "urn:schemas-upnp-org:device:InternetGatewayDevice:1",
        "ssdp_usn": MOCK_USN,
        "ssdp_location": f"https://{MOCK_HOST}:49000/",
        "ssdp_server": "Linux/3.10 UPnP/1.0 AVM FRITZ!Box 7530",
        "upnp": {ATTR_UPNP_FRIENDLY_NAME: "FRITZ!Box 7530", ATTR_UPNP_UDN: MOCK_UDN},
    }
    defaults.update(kwargs)
    return SsdpServiceInfo(**defaults)


def _flow_unique_id(flow: ConfigFlow) -> str | None:
    return flow.context.get("unique_id")


@pytest.mark.asyncio
async def test_ssdp_starts_confirm(hass: HomeAssistant) -> None:
    """SSDP discovery opens confirm step with device UUID."""
    flow = ConfigFlow()
    flow.hass = hass
    flow.handler = DOMAIN
    flow.context = {"source": SOURCE_SSDP}
    flow.init_step = SOURCE_SSDP
    flow.flow_id = "ssdp-test-flow"

    hass.config_entries.flow._progress[flow.flow_id] = flow

    mock_confirm = AsyncMock(return_value={"type": "form"})
    with (
        patch(
            "custom_components.fritzbox_vpn.config_flow.get_existing_fritz_config",
            new=AsyncMock(return_value=None),
        ),
        patch.object(flow, "async_step_confirm", mock_confirm),
    ):
        result = await flow.async_step_ssdp(_router_discovery())

    assert result == {"type": "form"}
    assert _flow_unique_id(flow) == MOCK_DEVICE_UUID
    assert flow._discovered_host == MOCK_HOST
    mock_confirm.assert_awaited_once()


@pytest.mark.asyncio
async def test_ssdp_aborts_when_already_configured(hass: HomeAssistant) -> None:
    """SSDP aborts if another Fritz integration already provides credentials."""
    flow = ConfigFlow()
    flow.hass = hass
    flow.handler = DOMAIN
    flow.context = {"source": SOURCE_SSDP}
    flow.flow_id = "ssdp-test-flow"
    hass.config_entries.flow._progress[flow.flow_id] = flow

    with patch(
        "custom_components.fritzbox_vpn.config_flow.get_existing_fritz_config",
        new=AsyncMock(
            return_value={"host": MOCK_HOST, "username": "u", "password": "p"},
        ),
    ):
        result = await flow.async_step_ssdp(_router_discovery())

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_ssdp_aborts_not_fritzbox(hass: HomeAssistant) -> None:
    """SSDP aborts for non-FRITZ SSDP payloads."""
    flow = ConfigFlow()
    flow.hass = hass
    flow.handler = DOMAIN
    flow.context = {"source": SOURCE_SSDP}
    flow.flow_id = "ssdp-test-flow"
    hass.config_entries.flow._progress[flow.flow_id] = flow

    discovery = SsdpServiceInfo(
        ssdp_st="urn:schemas-upnp-org:device:basic:1",
        ssdp_usn="uuid:other::device",
        ssdp_location="http://192.168.1.50/",
        ssdp_server="generic device",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "Other"},
    )
    with patch(
        "custom_components.fritzbox_vpn.config_flow.get_existing_fritz_config",
        new=AsyncMock(return_value=None),
    ):
        result = await flow.async_step_ssdp(discovery)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_fritzbox"


@pytest.mark.asyncio
async def test_ssdp_aborts_no_host(hass: HomeAssistant) -> None:
    """SSDP aborts when host cannot be resolved."""
    flow = ConfigFlow()
    flow.hass = hass
    flow.handler = DOMAIN
    flow.context = {"source": SOURCE_SSDP}
    flow.flow_id = "ssdp-test-flow"
    hass.config_entries.flow._progress[flow.flow_id] = flow

    discovery = SsdpServiceInfo(
        ssdp_st="urn:schemas-upnp-org:device:InternetGatewayDevice:1",
        ssdp_usn="mock_usn",
        ssdp_server="AVM FRITZ!Box 7530",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "FRITZ!Box"},
    )
    with patch(
        "custom_components.fritzbox_vpn.config_flow.get_existing_fritz_config",
        new=AsyncMock(return_value=None),
    ):
        result = await flow.async_step_ssdp(discovery)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_host"


@pytest.mark.asyncio
async def test_ssdp_aborts_link_local(hass: HomeAssistant) -> None:
    """SSDP aborts for link-local IPv6 hosts."""
    flow = ConfigFlow()
    flow.hass = hass
    flow.handler = DOMAIN
    flow.context = {"source": SOURCE_SSDP}
    flow.flow_id = "ssdp-test-flow"
    hass.config_entries.flow._progress[flow.flow_id] = flow

    discovery = _router_discovery(
        ssdp_location="https://[fe80::1ff:fe23:4567:890a]:49000/",
    )
    with patch(
        "custom_components.fritzbox_vpn.config_flow.get_existing_fritz_config",
        new=AsyncMock(return_value=None),
    ):
        result = await flow.async_step_ssdp(discovery)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_host"


@pytest.mark.asyncio
async def test_ssdp_accepts_fritz_box_hostname(hass: HomeAssistant) -> None:
    """SSDP accepts fritz.box hostname without link-local rejection."""
    flow = ConfigFlow()
    flow.hass = hass
    flow.handler = DOMAIN
    flow.context = {"source": SOURCE_SSDP}
    flow.flow_id = "ssdp-test-flow"
    hass.config_entries.flow._progress[flow.flow_id] = flow

    discovery = SsdpServiceInfo(
        ssdp_usn="uuid:device-1::upnp:rootdevice://fritz.box",
        ssdp_st="urn:schemas-upnp-org:device:InternetGatewayDevice:1",
        ssdp_server="AVM FRITZ!Box 7530",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "FRITZ!Box", ATTR_UPNP_UDN: MOCK_UDN},
    )
    mock_confirm = AsyncMock(return_value={"type": "form"})
    with (
        patch(
            "custom_components.fritzbox_vpn.config_flow.get_existing_fritz_config",
            new=AsyncMock(return_value=None),
        ),
        patch.object(flow, "async_step_confirm", mock_confirm),
    ):
        await flow.async_step_ssdp(discovery)

    assert flow._discovered_host == "fritz.box"
    assert _flow_unique_id(flow) == MOCK_DEVICE_UUID


@pytest.mark.asyncio
async def test_ssdp_host_unique_id_when_uuid_missing(hass: HomeAssistant) -> None:
    """SSDP uses host as unique_id when no device UUID is advertised."""
    flow = ConfigFlow()
    flow.hass = hass
    flow.handler = DOMAIN
    flow.context = {"source": SOURCE_SSDP}
    flow.init_step = SOURCE_SSDP
    flow.flow_id = "ssdp-test-flow"
    hass.config_entries.flow._progress[flow.flow_id] = flow

    discovery = _router_discovery(
        ssdp_usn="mock_usn",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "FRITZ!Box 7530"},
    )
    with (
        patch(
            "custom_components.fritzbox_vpn.config_flow.get_existing_fritz_config",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            flow,
            "async_step_confirm",
            AsyncMock(return_value={"type": "form"}),
        ),
    ):
        await flow.async_step_ssdp(discovery)

    assert _flow_unique_id(flow) == MOCK_HOST

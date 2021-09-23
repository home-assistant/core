"""Test the SSDP integration."""
from datetime import datetime, timedelta
from ipaddress import IPv4Address, IPv6Address
from unittest.mock import ANY, AsyncMock, patch

from async_upnp_client.ssdp import udn_from_headers
from async_upnp_client.ssdp_listener import SsdpListener
from async_upnp_client.utils import CaseInsensitiveDict
import pytest

import homeassistant
from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    MATCH_ALL,
)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed


def _ssdp_headers(headers):
    return CaseInsensitiveDict(
        headers, _timestamp=datetime(2021, 1, 1, 12, 00), _udn=udn_from_headers(headers)
    )


async def init_ssdp_component(hass: homeassistant) -> SsdpListener:
    """Initialize ssdp component and get SsdpListener."""
    await async_setup_component(hass, ssdp.DOMAIN, {ssdp.DOMAIN: {}})
    await hass.async_block_till_done()
    return hass.data[ssdp.DOMAIN]._ssdp_listeners[0]


@patch(
    "homeassistant.components.ssdp.async_get_ssdp",
    return_value={"mock-domain": [{"st": "mock-st"}]},
)
@pytest.mark.usefixtures("mock_get_source_ip")
async def test_ssdp_flow_dispatched_on_st(mock_get_ssdp, hass, caplog, mock_flow_init):
    """Test matching based on ST."""
    mock_ssdp_search_response = _ssdp_headers(
        {
            "st": "mock-st",
            "location": None,
            "usn": "uuid:mock-udn::mock-st",
            "server": "mock-server",
            "ext": "",
        }
    )
    ssdp_listener = await init_ssdp_component(hass)
    await ssdp_listener._on_search(mock_ssdp_search_response)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert len(mock_flow_init.mock_calls) == 1
    assert mock_flow_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_flow_init.mock_calls[0][2]["context"] == {
        "source": config_entries.SOURCE_SSDP
    }
    assert mock_flow_init.mock_calls[0][2]["data"] == {
        ssdp.ATTR_SSDP_ST: "mock-st",
        ssdp.ATTR_SSDP_LOCATION: None,
        ssdp.ATTR_SSDP_USN: "uuid:mock-udn::mock-st",
        ssdp.ATTR_SSDP_SERVER: "mock-server",
        ssdp.ATTR_SSDP_EXT: "",
        ssdp.ATTR_UPNP_UDN: "uuid:mock-udn",
        "_udn": ANY,
        "_timestamp": ANY,
    }
    assert "Failed to fetch ssdp data" not in caplog.text


@pytest.mark.usefixtures("mock_get_source_ip")
@patch(
    "homeassistant.components.ssdp.async_get_ssdp",
    return_value={"mock-domain": [{"manufacturer": "Paulus"}]},
)
async def test_scan_match_upnp_devicedesc_manufacturer(
    mock_get_ssdp, hass, aioclient_mock, mock_flow_init
):
    """Test matching based on UPnP device description data."""
    aioclient_mock.get(
        "http://1.1.1.1",
        text="""
<root>
  <device>
    <manufacturer>Paulus</manufacturer>
  </device>
</root>
    """,
    )
    mock_ssdp_search_response = _ssdp_headers(
        {
            "st": "mock-st",
            "location": "http://1.1.1.1",
            "usn": "uuid:mock-udn::mock-st",
        }
    )
    ssdp_listener = await init_ssdp_component(hass)
    await ssdp_listener._on_search(mock_ssdp_search_response)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    # If we get duplicate response, ensure we only look it up once
    assert len(aioclient_mock.mock_calls) == 1
    assert len(mock_flow_init.mock_calls) == 1
    assert mock_flow_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_flow_init.mock_calls[0][2]["context"] == {
        "source": config_entries.SOURCE_SSDP
    }


@pytest.mark.usefixtures("mock_get_source_ip")
@patch(
    "homeassistant.components.ssdp.async_get_ssdp",
    return_value={"mock-domain": [{"deviceType": "Paulus"}]},
)
async def test_scan_match_upnp_devicedesc_devicetype(
    mock_get_ssdp, hass, aioclient_mock, mock_flow_init
):
    """Test matching based on UPnP device description data."""
    aioclient_mock.get(
        "http://1.1.1.1",
        text="""
<root>
  <device>
    <deviceType>Paulus</deviceType>
  </device>
</root>
    """,
    )
    mock_ssdp_search_response = _ssdp_headers(
        {
            "st": "mock-st",
            "location": "http://1.1.1.1",
            "usn": "uuid:mock-udn::mock-st",
        }
    )
    ssdp_listener = await init_ssdp_component(hass)
    await ssdp_listener._on_search(mock_ssdp_search_response)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    # If we get duplicate response, ensure we only look it up once
    assert len(aioclient_mock.mock_calls) == 1
    assert len(mock_flow_init.mock_calls) == 1
    assert mock_flow_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_flow_init.mock_calls[0][2]["context"] == {
        "source": config_entries.SOURCE_SSDP
    }


@pytest.mark.usefixtures("mock_get_source_ip")
@patch(
    "homeassistant.components.ssdp.async_get_ssdp",
    return_value={
        "mock-domain": [
            {
                ssdp.ATTR_UPNP_DEVICE_TYPE: "Paulus",
                ssdp.ATTR_UPNP_MANUFACTURER: "Paulus",
            }
        ]
    },
)
async def test_scan_not_all_present(
    mock_get_ssdp, hass, aioclient_mock, mock_flow_init
):
    """Test match fails if some specified attributes are not present."""
    aioclient_mock.get(
        "http://1.1.1.1",
        text="""
<root>
  <device>
    <deviceType>Paulus</deviceType>
  </device>
</root>
    """,
    )
    mock_ssdp_search_response = _ssdp_headers(
        {
            "st": "mock-st",
            "location": "http://1.1.1.1",
        }
    )
    ssdp_listener = await init_ssdp_component(hass)
    await ssdp_listener._on_search(mock_ssdp_search_response)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert not mock_flow_init.mock_calls


@pytest.mark.usefixtures("mock_get_source_ip")
@patch(
    "homeassistant.components.ssdp.async_get_ssdp",
    return_value={
        "mock-domain": [
            {
                ssdp.ATTR_UPNP_DEVICE_TYPE: "Paulus",
                ssdp.ATTR_UPNP_MANUFACTURER: "Not-Paulus",
            }
        ]
    },
)
async def test_scan_not_all_match(mock_get_ssdp, hass, aioclient_mock, mock_flow_init):
    """Test match fails if some specified attribute values differ."""
    aioclient_mock.get(
        "http://1.1.1.1",
        text="""
<root>
  <device>
    <deviceType>Paulus</deviceType>
    <manufacturer>Paulus</manufacturer>
  </device>
</root>
    """,
    )
    mock_ssdp_search_response = _ssdp_headers(
        {
            "st": "mock-st",
            "location": "http://1.1.1.1",
            "usn": "uuid:mock-udn::mock-st",
        }
    )
    ssdp_listener = await init_ssdp_component(hass)
    await ssdp_listener._on_search(mock_ssdp_search_response)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert not mock_flow_init.mock_calls


@patch(  # XXX TODO: Isn't this duplicate with mock_get_source_ip?
    "homeassistant.components.ssdp.Scanner._async_build_source_set",
    return_value={IPv4Address("192.168.1.1")},
)
@pytest.mark.usefixtures("mock_get_source_ip")
async def test_start_stop_scanner(mock_source_set, hass):
    """Test we start and stop the scanner."""
    ssdp_listener = await init_ssdp_component(hass)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=200))
    await hass.async_block_till_done()
    assert ssdp_listener.async_start.call_count == 1
    assert ssdp_listener.async_search.call_count == 4
    assert ssdp_listener.async_stop.call_count == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=200))
    await hass.async_block_till_done()
    assert ssdp_listener.async_start.call_count == 1
    assert ssdp_listener.async_search.call_count == 4
    assert ssdp_listener.async_stop.call_count == 1


@pytest.mark.usefixtures("mock_get_source_ip")
@patch("homeassistant.components.ssdp.async_get_ssdp", return_value={})
async def test_scan_with_registered_callback(
    mock_get_ssdp, hass, aioclient_mock, caplog
):
    """Test matching based on callback."""
    aioclient_mock.get(
        "http://1.1.1.1",
        text="""
<root>
  <device>
    <deviceType>Paulus</deviceType>
  </device>
</root>
    """,
    )
    mock_ssdp_search_response = _ssdp_headers(
        {
            "st": "mock-st",
            "location": "http://1.1.1.1",
            "usn": "uuid:TIVRTLSR7ANF-D6E-1557809135086-RETAIL::mock-st",
            "server": "mock-server",
            "x-rincon-bootseq": "55",
            "ext": "",
        }
    )
    ssdp_listener = await init_ssdp_component(hass)

    async_exception_callback = AsyncMock(side_effect=ValueError)
    await ssdp.async_register_callback(hass, async_exception_callback, {})

    async_integration_callback = AsyncMock()
    await ssdp.async_register_callback(
        hass, async_integration_callback, {"st": "mock-st"}
    )

    async_integration_match_all_callback1 = AsyncMock()
    await ssdp.async_register_callback(
        hass, async_integration_match_all_callback1, {"x-rincon-bootseq": MATCH_ALL}
    )

    async_integration_match_all_not_present_callback1 = AsyncMock()
    await ssdp.async_register_callback(
        hass,
        async_integration_match_all_not_present_callback1,
        {"x-not-there": MATCH_ALL},
    )

    async_not_matching_integration_callback1 = AsyncMock()
    await ssdp.async_register_callback(
        hass, async_not_matching_integration_callback1, {"st": "not-match-mock-st"}
    )

    async_match_any_callback1 = AsyncMock()
    await ssdp.async_register_callback(hass, async_match_any_callback1)

    await hass.async_block_till_done()
    await ssdp_listener._on_search(mock_ssdp_search_response)

    assert async_integration_callback.call_count == 1
    assert async_integration_match_all_callback1.call_count == 1
    assert async_integration_match_all_not_present_callback1.call_count == 0
    assert async_match_any_callback1.call_count == 1
    assert async_not_matching_integration_callback1.call_count == 0
    assert async_integration_callback.call_args[0] == (
        {
            ssdp.ATTR_UPNP_DEVICE_TYPE: "Paulus",
            ssdp.ATTR_SSDP_EXT: "",
            ssdp.ATTR_SSDP_LOCATION: "http://1.1.1.1",
            ssdp.ATTR_SSDP_SERVER: "mock-server",
            ssdp.ATTR_SSDP_ST: "mock-st",
            ssdp.ATTR_SSDP_USN: "uuid:TIVRTLSR7ANF-D6E-1557809135086-RETAIL::mock-st",
            ssdp.ATTR_UPNP_UDN: "uuid:TIVRTLSR7ANF-D6E-1557809135086-RETAIL",
            "x-rincon-bootseq": "55",
            "_udn": ANY,
            "_timestamp": ANY,
        },
        ssdp.SsdpChange.ALIVE,
    )
    assert "Failed to callback info" in caplog.text

    async_integration_callback_from_cache = AsyncMock()
    await ssdp.async_register_callback(
        hass, async_integration_callback_from_cache, {"st": "mock-st"}
    )

    assert async_integration_callback_from_cache.call_count == 1


@pytest.mark.usefixtures("mock_get_source_ip")
@patch(
    "homeassistant.components.ssdp.async_get_ssdp",
    return_value={"mock-domain": [{"st": "mock-st"}]},
)
async def test_getting_existing_headers(mock_get_ssdp, hass, aioclient_mock):
    """Test getting existing/previously scanned headers."""
    aioclient_mock.get(
        "http://1.1.1.1",
        text="""
<root>
  <device>
    <deviceType>Paulus</deviceType>
  </device>
</root>
    """,
    )
    mock_ssdp_search_response = _ssdp_headers(
        {
            "ST": "mock-st",
            "LOCATION": "http://1.1.1.1",
            "USN": "uuid:TIVRTLSR7ANF-D6E-1557809135086-RETAIL::urn:mdx-netflix-com:service:target:3",
            "SERVER": "mock-server",
            "EXT": "",
        }
    )
    ssdp_listener = await init_ssdp_component(hass)
    await ssdp_listener._on_search(mock_ssdp_search_response)

    discovery_info_by_st = await ssdp.async_get_discovery_info_by_st(hass, "mock-st")
    assert discovery_info_by_st == [
        {
            ssdp.ATTR_SSDP_EXT: "",
            ssdp.ATTR_SSDP_LOCATION: "http://1.1.1.1",
            ssdp.ATTR_SSDP_SERVER: "mock-server",
            ssdp.ATTR_SSDP_ST: "mock-st",
            ssdp.ATTR_SSDP_USN: "uuid:TIVRTLSR7ANF-D6E-1557809135086-RETAIL::urn:mdx-netflix-com:service:target:3",
            ssdp.ATTR_UPNP_UDN: "uuid:TIVRTLSR7ANF-D6E-1557809135086-RETAIL",
            ssdp.ATTR_UPNP_DEVICE_TYPE: "Paulus",
            "_udn": ANY,
            "_timestamp": ANY,
        }
    ]

    discovery_info_by_udn = await ssdp.async_get_discovery_info_by_udn(
        hass, "uuid:TIVRTLSR7ANF-D6E-1557809135086-RETAIL"
    )
    assert discovery_info_by_udn == [
        {
            ssdp.ATTR_SSDP_EXT: "",
            ssdp.ATTR_SSDP_LOCATION: "http://1.1.1.1",
            ssdp.ATTR_SSDP_SERVER: "mock-server",
            ssdp.ATTR_SSDP_ST: "mock-st",
            ssdp.ATTR_SSDP_USN: "uuid:TIVRTLSR7ANF-D6E-1557809135086-RETAIL::urn:mdx-netflix-com:service:target:3",
            ssdp.ATTR_UPNP_UDN: "uuid:TIVRTLSR7ANF-D6E-1557809135086-RETAIL",
            ssdp.ATTR_UPNP_DEVICE_TYPE: "Paulus",
            "_udn": ANY,
            "_timestamp": ANY,
        }
    ]

    discovery_info_by_udn_st = await ssdp.async_get_discovery_info_by_udn_st(
        hass, "uuid:TIVRTLSR7ANF-D6E-1557809135086-RETAIL", "mock-st"
    )
    assert discovery_info_by_udn_st == {
        ssdp.ATTR_SSDP_EXT: "",
        ssdp.ATTR_SSDP_LOCATION: "http://1.1.1.1",
        ssdp.ATTR_SSDP_SERVER: "mock-server",
        ssdp.ATTR_SSDP_ST: "mock-st",
        ssdp.ATTR_SSDP_USN: "uuid:TIVRTLSR7ANF-D6E-1557809135086-RETAIL::urn:mdx-netflix-com:service:target:3",
        ssdp.ATTR_UPNP_UDN: "uuid:TIVRTLSR7ANF-D6E-1557809135086-RETAIL",
        ssdp.ATTR_UPNP_DEVICE_TYPE: "Paulus",
        "_udn": ANY,
        "_timestamp": ANY,
    }

    assert (
        await ssdp.async_get_discovery_info_by_udn_st(hass, "wrong", "mock-st") is None
    )


_ADAPTERS_WITH_MANUAL_CONFIG = [
    {
        "auto": True,
        "default": False,
        "enabled": True,
        "ipv4": [],
        "ipv6": [
            {
                "address": "2001:db8::",
                "network_prefix": 8,
                "flowinfo": 1,
                "scope_id": 1,
            }
        ],
        "name": "eth0",
    },
    {
        "auto": True,
        "default": False,
        "enabled": True,
        "ipv4": [{"address": "192.168.1.5", "network_prefix": 23}],
        "ipv6": [],
        "name": "eth1",
    },
    {
        "auto": False,
        "default": False,
        "enabled": False,
        "ipv4": [{"address": "169.254.3.2", "network_prefix": 16}],
        "ipv6": [],
        "name": "vtun0",
    },
]


@pytest.mark.usefixtures("mock_get_source_ip")
@patch(
    "homeassistant.components.ssdp.async_get_ssdp",
    return_value={
        "mock-domain": [
            {
                ssdp.ATTR_UPNP_DEVICE_TYPE: "ABC",
            }
        ]
    },
)
@patch(
    "homeassistant.components.ssdp.network.async_get_adapters",
    return_value=_ADAPTERS_WITH_MANUAL_CONFIG,
)  # XXX TODO: Isn't this duplicate with mock_get_source_ip?
async def test_async_detect_interfaces_setting_empty_route(
    mock_get_adapters, mock_get_ssdp, hass
):
    """Test without default interface config and the route returns nothing."""
    await init_ssdp_component(hass)

    ssdp_listeners = hass.data[ssdp.DOMAIN]._ssdp_listeners
    source_ips = {ssdp_listener.source_ip for ssdp_listener in ssdp_listeners}
    assert source_ips == {IPv6Address("2001:db8::"), IPv4Address("192.168.1.5")}


@pytest.mark.usefixtures("mock_get_source_ip")
@patch(
    "homeassistant.components.ssdp.async_get_ssdp",
    return_value={
        "mock-domain": [
            {
                ssdp.ATTR_UPNP_DEVICE_TYPE: "ABC",
            }
        ]
    },
)
@patch(
    "homeassistant.components.ssdp.network.async_get_adapters",
    return_value=_ADAPTERS_WITH_MANUAL_CONFIG,
)  # XXX TODO: Isn't this duplicate with mock_get_source_ip?
async def test_bind_failure_skips_adapter(
    mock_get_adapters, mock_get_ssdp, hass, caplog
):
    """Test that an adapter with a bind failure is skipped."""

    async def _async_start(self):
        if self.source_ip == IPv6Address("2001:db8::"):
            raise OSError

    SsdpListener.async_start = _async_start
    await init_ssdp_component(hass)

    assert "Failed to setup listener for" in caplog.text

    ssdp_listeners = hass.data[ssdp.DOMAIN]._ssdp_listeners
    source_ips = {ssdp_listener.source_ip for ssdp_listener in ssdp_listeners}
    assert source_ips == {
        IPv4Address("192.168.1.5")
    }  # Note no SsdpListener for IPv6 address.


@pytest.mark.usefixtures("mock_get_source_ip")
@patch(
    "homeassistant.components.ssdp.async_get_ssdp",
    return_value={
        "mock-domain": [
            {
                ssdp.ATTR_UPNP_DEVICE_TYPE: "ABC",
            }
        ]
    },
)
@patch(
    "homeassistant.components.ssdp.network.async_get_adapters",
    return_value=_ADAPTERS_WITH_MANUAL_CONFIG,
)  # XXX TODO: Isn't this duplicate with mock_get_source_ip?
async def test_ipv4_does_additional_search_for_sonos(
    mock_get_adapters, mock_get_ssdp, hass
):
    """Test that only ipv4 does an additional search for Sonos."""
    ssdp_listener = await init_ssdp_component(hass)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=200))
    await hass.async_block_till_done()

    assert ssdp_listener.async_search.call_count == 6
    assert ssdp_listener.async_search.call_args[0] == (
        (
            "255.255.255.255",
            1900,
        ),
    )
    assert ssdp_listener.async_search.call_args[1] == {}

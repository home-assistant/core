"""Test the SSDP integration."""

from datetime import datetime
from ipaddress import IPv4Address
from unittest.mock import ANY, AsyncMock, patch

from async_upnp_client.server import UpnpServer
from async_upnp_client.ssdp import udn_from_headers
from async_upnp_client.ssdp_listener import SsdpListener
from async_upnp_client.utils import CaseInsensitiveDict
import pytest

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    MATCH_ALL,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


def _ssdp_headers(headers):
    ssdp_headers = CaseInsensitiveDict(headers, _timestamp=datetime.now())
    ssdp_headers["_udn"] = udn_from_headers(ssdp_headers)
    return ssdp_headers


async def init_ssdp_component(hass: HomeAssistant) -> SsdpListener:
    """Initialize ssdp component and get SsdpListener."""
    await async_setup_component(hass, ssdp.DOMAIN, {ssdp.DOMAIN: {}})
    await hass.async_block_till_done()
    return hass.data[ssdp.DOMAIN][ssdp.SSDP_SCANNER]._ssdp_listeners[0]


@patch(
    "homeassistant.components.ssdp.async_get_ssdp",
    return_value={"mock-domain": [{"st": "mock-st"}]},
)
@pytest.mark.usefixtures("mock_get_source_ip")
async def test_ssdp_flow_dispatched_on_st(
    mock_get_ssdp, hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_flow_init
) -> None:
    """Test matching based on ST."""
    mock_ssdp_search_response = _ssdp_headers(
        {
            "st": "mock-st",
            "location": "http://1.1.1.1",
            "usn": "uuid:mock-udn::mock-st",
            "server": "mock-server",
            "ext": "",
            "_source": "search",
        }
    )
    ssdp_listener = await init_ssdp_component(hass)
    ssdp_listener._on_search(mock_ssdp_search_response)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert len(mock_flow_init.mock_calls) == 1
    assert mock_flow_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_flow_init.mock_calls[0][2]["context"] == {
        "source": config_entries.SOURCE_SSDP
    }
    mock_call_data: ssdp.SsdpServiceInfo = mock_flow_init.mock_calls[0][2]["data"]
    assert mock_call_data.ssdp_st == "mock-st"
    assert mock_call_data.ssdp_location == "http://1.1.1.1"
    assert mock_call_data.ssdp_usn == "uuid:mock-udn::mock-st"
    assert mock_call_data.ssdp_server == "mock-server"
    assert mock_call_data.ssdp_ext == ""
    assert mock_call_data.ssdp_udn == ANY
    assert mock_call_data.ssdp_headers["_timestamp"] == ANY
    assert mock_call_data.x_homeassistant_matching_domains == {"mock-domain"}
    assert mock_call_data.upnp == {ssdp.ATTR_UPNP_UDN: "uuid:mock-udn"}
    assert "Failed to fetch ssdp data" not in caplog.text


@patch(
    "homeassistant.components.ssdp.async_get_ssdp",
    return_value={"mock-domain": [{"manufacturerURL": "mock-url"}]},
)
@pytest.mark.usefixtures("mock_get_source_ip")
async def test_ssdp_flow_dispatched_on_manufacturer_url(
    mock_get_ssdp, hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_flow_init
) -> None:
    """Test matching based on manufacturerURL."""
    mock_ssdp_search_response = _ssdp_headers(
        {
            "st": "mock-st",
            "manufacturerURL": "mock-url",
            "location": "http://1.1.1.1",
            "usn": "uuid:mock-udn::mock-st",
            "server": "mock-server",
            "ext": "",
            "_source": "search",
        }
    )
    ssdp_listener = await init_ssdp_component(hass)
    ssdp_listener._on_search(mock_ssdp_search_response)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert len(mock_flow_init.mock_calls) == 1
    assert mock_flow_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_flow_init.mock_calls[0][2]["context"] == {
        "source": config_entries.SOURCE_SSDP
    }
    mock_call_data: ssdp.SsdpServiceInfo = mock_flow_init.mock_calls[0][2]["data"]
    assert mock_call_data.ssdp_st == "mock-st"
    assert mock_call_data.ssdp_location == "http://1.1.1.1"
    assert mock_call_data.ssdp_usn == "uuid:mock-udn::mock-st"
    assert mock_call_data.ssdp_server == "mock-server"
    assert mock_call_data.ssdp_ext == ""
    assert mock_call_data.ssdp_udn == ANY
    assert mock_call_data.ssdp_headers["_timestamp"] == ANY
    assert mock_call_data.x_homeassistant_matching_domains == {"mock-domain"}
    assert mock_call_data.upnp == {ssdp.ATTR_UPNP_UDN: "uuid:mock-udn"}
    assert "Failed to fetch ssdp data" not in caplog.text


@pytest.mark.usefixtures("mock_get_source_ip")
@patch(
    "homeassistant.components.ssdp.async_get_ssdp",
    return_value={"mock-domain": [{"manufacturer": "Paulus"}]},
)
async def test_scan_match_upnp_devicedesc_manufacturer(
    mock_get_ssdp,
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_flow_init,
) -> None:
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
            "_source": "search",
        }
    )
    ssdp_listener = await init_ssdp_component(hass)
    ssdp_listener._on_search(mock_ssdp_search_response)
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
    mock_get_ssdp,
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_flow_init,
) -> None:
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
            "_source": "search",
        }
    )
    ssdp_listener = await init_ssdp_component(hass)
    ssdp_listener._on_search(mock_ssdp_search_response)
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
    mock_get_ssdp,
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_flow_init,
) -> None:
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
    ssdp_listener._on_search(mock_ssdp_search_response)
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
async def test_scan_not_all_match(
    mock_get_ssdp,
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_flow_init,
) -> None:
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
            "_source": "search",
        }
    )
    ssdp_listener = await init_ssdp_component(hass)
    ssdp_listener._on_search(mock_ssdp_search_response)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert not mock_flow_init.mock_calls


@pytest.mark.usefixtures("mock_get_source_ip")
@patch(
    "homeassistant.components.ssdp.async_get_ssdp",
    return_value={"mock-domain": [{"deviceType": "Paulus"}]},
)
async def test_flow_start_only_alive(
    mock_get_ssdp,
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_flow_init,
) -> None:
    """Test config flow is only started for alive devices."""
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
    ssdp_listener = await init_ssdp_component(hass)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    # Search should start a flow
    mock_ssdp_search_response = _ssdp_headers(
        {
            "st": "mock-st",
            "location": "http://1.1.1.1",
            "usn": "uuid:mock-udn::mock-st",
            "_source": "search",
        }
    )
    ssdp_listener._on_search(mock_ssdp_search_response)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_flow_init.assert_awaited_once_with(
        "mock-domain", context={"source": config_entries.SOURCE_SSDP}, data=ANY
    )

    # ssdp:alive advertisement should start a flow
    mock_flow_init.reset_mock()
    mock_ssdp_advertisement = _ssdp_headers(
        {
            "location": "http://1.1.1.1",
            "usn": "uuid:mock-udn::mock-st",
            "nt": "upnp:rootdevice",
            "nts": "ssdp:alive",
            "_source": "advertisement",
        }
    )
    ssdp_listener._on_alive(mock_ssdp_advertisement)
    await hass.async_block_till_done()
    mock_flow_init.assert_awaited_once_with(
        "mock-domain", context={"source": config_entries.SOURCE_SSDP}, data=ANY
    )

    # ssdp:byebye advertisement should not start a flow
    mock_flow_init.reset_mock()
    mock_ssdp_advertisement["nts"] = "ssdp:byebye"
    ssdp_listener._on_byebye(mock_ssdp_advertisement)
    await hass.async_block_till_done()
    mock_flow_init.assert_not_called()

    # ssdp:update advertisement should start a flow
    mock_flow_init.reset_mock()
    mock_ssdp_advertisement["nts"] = "ssdp:update"
    ssdp_listener._on_update(mock_ssdp_advertisement)
    await hass.async_block_till_done()
    mock_flow_init.assert_awaited_once_with(
        "mock-domain", context={"source": config_entries.SOURCE_SSDP}, data=ANY
    )


@pytest.mark.usefixtures("mock_get_source_ip")
@patch(
    "homeassistant.components.ssdp.async_get_ssdp",
    return_value={},
)
async def test_discovery_from_advertisement_sets_ssdp_st(
    mock_get_ssdp,
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_flow_init,
) -> None:
    """Test discovery from advertisement sets `ssdp_st` for more compatibility."""
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
    ssdp_listener = await init_ssdp_component(hass)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    mock_ssdp_advertisement = _ssdp_headers(
        {
            "nt": "mock-st",
            "nts": "ssdp:alive",
            "location": "http://1.1.1.1",
            "usn": "uuid:mock-udn::mock-st",
            "_source": "advertisement",
        }
    )
    ssdp_listener._on_alive(mock_ssdp_advertisement)
    await hass.async_block_till_done()

    discovery_info = await ssdp.async_get_discovery_info_by_udn(hass, "uuid:mock-udn")
    discovery_info = discovery_info[0]
    assert discovery_info.ssdp_location == "http://1.1.1.1"
    assert discovery_info.ssdp_nt == "mock-st"
    # Set by ssdp component, not in original advertisement.
    assert discovery_info.ssdp_st == "mock-st"
    assert discovery_info.ssdp_usn == "uuid:mock-udn::mock-st"
    assert discovery_info.ssdp_udn == ANY
    assert discovery_info.ssdp_headers["nts"] == "ssdp:alive"
    assert discovery_info.ssdp_headers["_timestamp"] == ANY
    assert discovery_info.upnp == {
        ssdp.ATTR_UPNP_DEVICE_TYPE: "Paulus",
        ssdp.ATTR_UPNP_UDN: "uuid:mock-udn",
    }


@patch(
    "homeassistant.components.ssdp.async_build_source_set",
    return_value={IPv4Address("192.168.1.1")},
)
@pytest.mark.usefixtures("mock_get_source_ip")
async def test_start_stop_scanner(mock_source_set, hass: HomeAssistant) -> None:
    """Test we start and stop the scanner."""
    ssdp_listener = await init_ssdp_component(hass)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + ssdp.SCAN_INTERVAL)
    await hass.async_block_till_done()
    assert ssdp_listener.async_start.call_count == 1
    assert ssdp_listener.async_search.call_count == 4
    assert ssdp_listener.async_stop.call_count == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + ssdp.SCAN_INTERVAL)
    await hass.async_block_till_done()
    assert ssdp_listener.async_start.call_count == 1
    assert ssdp_listener.async_search.call_count == 4
    assert ssdp_listener.async_stop.call_count == 1


@pytest.mark.usefixtures("mock_get_source_ip")
@pytest.mark.no_fail_on_log_exception
@patch("homeassistant.components.ssdp.async_get_ssdp", return_value={})
async def test_scan_with_registered_callback(
    mock_get_ssdp,
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
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
            "_source": "search",
        }
    )
    ssdp_listener = await init_ssdp_component(hass)

    async_exception_callback = AsyncMock(side_effect=ValueError)
    await ssdp.async_register_callback(hass, async_exception_callback, {})

    async_integration_callback = AsyncMock()
    await ssdp.async_register_callback(
        hass, async_integration_callback, {"st": "mock-st"}
    )

    async_integration_match_all_callback = AsyncMock()
    await ssdp.async_register_callback(
        hass, async_integration_match_all_callback, {"x-rincon-bootseq": MATCH_ALL}
    )

    async_integration_match_all_not_present_callback = AsyncMock()
    await ssdp.async_register_callback(
        hass,
        async_integration_match_all_not_present_callback,
        {"x-not-there": MATCH_ALL},
    )

    async_not_matching_integration_callback = AsyncMock()
    await ssdp.async_register_callback(
        hass, async_not_matching_integration_callback, {"st": "not-match-mock-st"}
    )

    async_match_any_callback = AsyncMock()
    await ssdp.async_register_callback(hass, async_match_any_callback)

    await hass.async_block_till_done(wait_background_tasks=True)
    ssdp_listener._on_search(mock_ssdp_search_response)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert async_integration_callback.call_count == 1
    assert async_integration_match_all_callback.call_count == 1
    assert async_integration_match_all_not_present_callback.call_count == 0
    assert async_match_any_callback.call_count == 1
    assert async_not_matching_integration_callback.call_count == 0
    assert async_integration_callback.call_args[0][1] == ssdp.SsdpChange.ALIVE
    mock_call_data: ssdp.SsdpServiceInfo = async_integration_callback.call_args[0][0]
    assert mock_call_data.ssdp_ext == ""
    assert mock_call_data.ssdp_location == "http://1.1.1.1"
    assert mock_call_data.ssdp_server == "mock-server"
    assert mock_call_data.ssdp_st == "mock-st"
    assert (
        mock_call_data.ssdp_usn == "uuid:TIVRTLSR7ANF-D6E-1557809135086-RETAIL::mock-st"
    )
    assert mock_call_data.ssdp_headers["x-rincon-bootseq"] == "55"
    assert mock_call_data.ssdp_udn == "uuid:TIVRTLSR7ANF-D6E-1557809135086-RETAIL"
    assert mock_call_data.ssdp_headers["_timestamp"] == ANY
    assert mock_call_data.x_homeassistant_matching_domains == set()
    assert mock_call_data.upnp == {
        ssdp.ATTR_UPNP_DEVICE_TYPE: "Paulus",
        ssdp.ATTR_UPNP_UDN: "uuid:TIVRTLSR7ANF-D6E-1557809135086-RETAIL",
    }
    assert "Exception in SSDP callback" in caplog.text

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
async def test_getting_existing_headers(
    mock_get_ssdp,
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_flow_init,
) -> None:
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
            "_source": "search",
        }
    )
    ssdp_listener = await init_ssdp_component(hass)
    ssdp_listener._on_search(mock_ssdp_search_response)

    discovery_info_by_st = await ssdp.async_get_discovery_info_by_st(hass, "mock-st")
    discovery_info_by_st = discovery_info_by_st[0]
    assert discovery_info_by_st.ssdp_ext == ""
    assert discovery_info_by_st.ssdp_location == "http://1.1.1.1"
    assert discovery_info_by_st.ssdp_server == "mock-server"
    assert discovery_info_by_st.ssdp_st == "mock-st"
    assert (
        discovery_info_by_st.ssdp_usn
        == "uuid:TIVRTLSR7ANF-D6E-1557809135086-RETAIL::urn:mdx-netflix-com:service:target:3"
    )
    assert discovery_info_by_st.ssdp_udn == ANY
    assert discovery_info_by_st.ssdp_headers["_timestamp"] == ANY
    assert discovery_info_by_st.upnp == {
        ssdp.ATTR_UPNP_DEVICE_TYPE: "Paulus",
        ssdp.ATTR_UPNP_UDN: "uuid:TIVRTLSR7ANF-D6E-1557809135086-RETAIL",
    }

    discovery_info_by_udn = await ssdp.async_get_discovery_info_by_udn(
        hass, "uuid:TIVRTLSR7ANF-D6E-1557809135086-RETAIL"
    )
    discovery_info_by_udn = discovery_info_by_udn[0]
    assert discovery_info_by_udn.ssdp_ext == ""
    assert discovery_info_by_udn.ssdp_location == "http://1.1.1.1"
    assert discovery_info_by_udn.ssdp_server == "mock-server"
    assert discovery_info_by_udn.ssdp_st == "mock-st"
    assert (
        discovery_info_by_udn.ssdp_usn
        == "uuid:TIVRTLSR7ANF-D6E-1557809135086-RETAIL::urn:mdx-netflix-com:service:target:3"
    )
    assert discovery_info_by_udn.ssdp_udn == ANY
    assert discovery_info_by_udn.ssdp_headers["_timestamp"] == ANY
    assert discovery_info_by_udn.upnp == {
        ssdp.ATTR_UPNP_DEVICE_TYPE: "Paulus",
        ssdp.ATTR_UPNP_UDN: "uuid:TIVRTLSR7ANF-D6E-1557809135086-RETAIL",
    }

    discovery_info_by_udn_st = await ssdp.async_get_discovery_info_by_udn_st(
        hass, "uuid:TIVRTLSR7ANF-D6E-1557809135086-RETAIL", "mock-st"
    )
    assert discovery_info_by_udn_st.ssdp_ext == ""
    assert discovery_info_by_udn_st.ssdp_location == "http://1.1.1.1"
    assert discovery_info_by_udn_st.ssdp_server == "mock-server"
    assert discovery_info_by_udn_st.ssdp_st == "mock-st"
    assert (
        discovery_info_by_udn_st.ssdp_usn
        == "uuid:TIVRTLSR7ANF-D6E-1557809135086-RETAIL::urn:mdx-netflix-com:service:target:3"
    )
    assert discovery_info_by_udn_st.ssdp_udn == ANY
    assert discovery_info_by_udn_st.ssdp_headers["_timestamp"] == ANY
    assert discovery_info_by_udn_st.upnp == {
        ssdp.ATTR_UPNP_DEVICE_TYPE: "Paulus",
        ssdp.ATTR_UPNP_UDN: "uuid:TIVRTLSR7ANF-D6E-1557809135086-RETAIL",
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
)
async def test_async_detect_interfaces_setting_empty_route(
    mock_get_adapters, mock_get_ssdp, hass: HomeAssistant
) -> None:
    """Test without default interface config and the route returns nothing."""
    await init_ssdp_component(hass)

    ssdp_listeners = hass.data[ssdp.DOMAIN][ssdp.SSDP_SCANNER]._ssdp_listeners
    sources = {ssdp_listener.source for ssdp_listener in ssdp_listeners}
    assert sources == {("2001:db8::", 0, 0, 1), ("192.168.1.5", 0)}


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
)
async def test_bind_failure_skips_adapter(
    mock_get_adapters,
    mock_get_ssdp,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that an adapter with a bind failure is skipped."""

    async def _async_start(self):
        if self.source == ("2001:db8::", 0, 0, 1):
            raise OSError

    SsdpListener.async_start = _async_start
    UpnpServer.async_start = _async_start
    await init_ssdp_component(hass)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert "Failed to setup listener for" in caplog.text

    ssdp_listeners: list[SsdpListener] = hass.data[ssdp.DOMAIN][
        ssdp.SSDP_SCANNER
    ]._ssdp_listeners
    sources = {ssdp_listener.source for ssdp_listener in ssdp_listeners}
    assert sources == {("192.168.1.5", 0)}  # Note no SsdpListener for IPv6 address.

    assert "Failed to setup server for" in caplog.text

    upnp_servers: list[UpnpServer] = hass.data[ssdp.DOMAIN][
        ssdp.UPNP_SERVER
    ]._upnp_servers
    sources = {upnp_server.source for upnp_server in upnp_servers}
    assert sources == {("192.168.1.5", 0)}  # Note no UpnpServer for IPv6 address.


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
)
async def test_ipv4_does_additional_search_for_sonos(
    mock_get_adapters, mock_get_ssdp, hass: HomeAssistant
) -> None:
    """Test that only ipv4 does an additional search for Sonos."""
    ssdp_listener = await init_ssdp_component(hass)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + ssdp.SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert ssdp_listener.async_search.call_count == 6
    assert ssdp_listener.async_search.call_args[0] == (
        (
            "255.255.255.255",
            1900,
        ),
    )
    assert ssdp_listener.async_search.call_args[1] == {}


@pytest.mark.usefixtures("mock_get_source_ip")
@patch(
    "homeassistant.components.ssdp.async_get_ssdp",
    return_value={"mock-domain": [{"deviceType": "Paulus"}]},
)
async def test_flow_dismiss_on_byebye(
    mock_get_ssdp,
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_flow_init,
) -> None:
    """Test config flow is only started for alive devices."""
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
    ssdp_listener = await init_ssdp_component(hass)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    # Search should start a flow
    mock_ssdp_search_response = _ssdp_headers(
        {
            "st": "mock-st",
            "location": "http://1.1.1.1",
            "usn": "uuid:mock-udn::mock-st",
            "_source": "search",
        }
    )
    ssdp_listener._on_search(mock_ssdp_search_response)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_flow_init.assert_awaited_once_with(
        "mock-domain", context={"source": config_entries.SOURCE_SSDP}, data=ANY
    )

    # ssdp:alive advertisement should start a flow
    mock_flow_init.reset_mock()
    mock_ssdp_advertisement = _ssdp_headers(
        {
            "location": "http://1.1.1.1",
            "usn": "uuid:mock-udn::mock-st",
            "nt": "upnp:rootdevice",
            "nts": "ssdp:alive",
            "_source": "advertisement",
        }
    )
    ssdp_listener._on_alive(mock_ssdp_advertisement)
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_flow_init.assert_awaited_once_with(
        "mock-domain", context={"source": config_entries.SOURCE_SSDP}, data=ANY
    )

    mock_ssdp_advertisement["nts"] = "ssdp:byebye"
    # ssdp:byebye advertisement should dismiss existing flows
    with (
        patch.object(
            hass.config_entries.flow,
            "async_progress_by_init_data_type",
            return_value=[{"flow_id": "mock_flow_id"}],
        ) as mock_async_progress_by_init_data_type,
        patch.object(hass.config_entries.flow, "async_abort") as mock_async_abort,
    ):
        ssdp_listener._on_byebye(mock_ssdp_advertisement)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert len(mock_async_progress_by_init_data_type.mock_calls) == 1
    assert mock_async_abort.mock_calls[0][1][0] == "mock_flow_id"

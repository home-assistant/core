"""Test the SSDP integration."""
import asyncio
from datetime import timedelta
from unittest.mock import patch

import aiohttp
from async_upnp_client.search import SSDPListener
import pytest

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed, mock_coro


def _patched_ssdp_listener(info, *args, **kwargs):
    listener = SSDPListener(*args, **kwargs)

    async def _async_callback():
        await listener.async_callback(info)

    listener.async_start = _async_callback
    return listener


async def _async_run_mocked_scan(hass, mock_ssdp_response, mock_get_ssdp):
    def _generate_fake_ssdp_listener(*args, **kwargs):
        return _patched_ssdp_listener(
            mock_ssdp_response,
            *args,
            **kwargs,
        )

    with patch(
        "homeassistant.components.ssdp.async_get_ssdp",
        return_value=mock_get_ssdp,
    ), patch(
        "homeassistant.components.ssdp.SSDPListener",
        new=_generate_fake_ssdp_listener,
    ), patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
        assert await async_setup_component(hass, ssdp.DOMAIN, {ssdp.DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    return mock_init


async def test_scan_match_st(hass, caplog):
    """Test matching based on ST."""
    mock_ssdp_response = {
        "st": "mock-st",
        "location": None,
        "usn": "mock-usn",
        "server": "mock-server",
        "ext": "",
    }
    mock_get_ssdp = {"mock-domain": [{"st": "mock-st"}]}
    mock_init = await _async_run_mocked_scan(hass, mock_ssdp_response, mock_get_ssdp)

    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_init.mock_calls[0][2]["context"] == {
        "source": config_entries.SOURCE_SSDP
    }
    assert mock_init.mock_calls[0][2]["data"] == {
        ssdp.ATTR_SSDP_ST: "mock-st",
        ssdp.ATTR_SSDP_LOCATION: None,
        ssdp.ATTR_SSDP_USN: "mock-usn",
        ssdp.ATTR_SSDP_SERVER: "mock-server",
        ssdp.ATTR_SSDP_EXT: "",
    }
    assert "Failed to fetch ssdp data" not in caplog.text


@pytest.mark.parametrize(
    "key", (ssdp.ATTR_UPNP_MANUFACTURER, ssdp.ATTR_UPNP_DEVICE_TYPE)
)
async def test_scan_match_upnp_devicedesc(hass, aioclient_mock, key):
    """Test matching based on UPnP device description data."""
    aioclient_mock.get(
        "http://1.1.1.1",
        text=f"""
<root>
  <device>
    <{key}>Paulus</{key}>
  </device>
</root>
    """,
    )
    mock_get_ssdp = {"mock-domain": [{key: "Paulus"}]}
    mock_ssdp_response = {
        "st": "mock-st",
        "location": "http://1.1.1.1",
    }
    mock_init = await _async_run_mocked_scan(hass, mock_ssdp_response, mock_get_ssdp)
    # If we get duplicate respones, ensure we only look it up once
    assert len(aioclient_mock.mock_calls) == 1
    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_init.mock_calls[0][2]["context"] == {
        "source": config_entries.SOURCE_SSDP
    }


async def test_scan_not_all_present(hass, aioclient_mock):
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
    mock_ssdp_response = {
        "st": "mock-st",
        "location": "http://1.1.1.1",
    }
    mock_get_ssdp = {
        "mock-domain": [
            {
                ssdp.ATTR_UPNP_DEVICE_TYPE: "Paulus",
                ssdp.ATTR_UPNP_MANUFACTURER: "Paulus",
            }
        ]
    }
    mock_init = await _async_run_mocked_scan(hass, mock_ssdp_response, mock_get_ssdp)

    assert not mock_init.mock_calls


async def test_scan_not_all_match(hass, aioclient_mock):
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
    mock_ssdp_response = {
        "st": "mock-st",
        "location": "http://1.1.1.1",
    }
    mock_get_ssdp = {
        "mock-domain": [
            {
                ssdp.ATTR_UPNP_DEVICE_TYPE: "Paulus",
                ssdp.ATTR_UPNP_MANUFACTURER: "Not-Paulus",
            }
        ]
    }
    mock_init = await _async_run_mocked_scan(hass, mock_ssdp_response, mock_get_ssdp)

    assert not mock_init.mock_calls


@pytest.mark.parametrize("exc", [asyncio.TimeoutError, aiohttp.ClientError])
async def test_scan_description_fetch_fail(hass, aioclient_mock, exc):
    """Test failing to fetch description."""
    aioclient_mock.get("http://1.1.1.1", exc=exc)
    mock_ssdp_response = {
        "st": "mock-st",
        "location": "http://1.1.1.1",
    }
    mock_get_ssdp = {
        "mock-domain": [
            {
                ssdp.ATTR_UPNP_DEVICE_TYPE: "Paulus",
                ssdp.ATTR_UPNP_MANUFACTURER: "Paulus",
            }
        ]
    }
    mock_init = await _async_run_mocked_scan(hass, mock_ssdp_response, mock_get_ssdp)

    assert not mock_init.mock_calls


async def test_scan_description_parse_fail(hass, aioclient_mock):
    """Test invalid XML."""
    aioclient_mock.get(
        "http://1.1.1.1",
        text="""
<root>INVALIDXML
    """,
    )

    mock_ssdp_response = {
        "st": "mock-st",
        "location": "http://1.1.1.1",
    }
    mock_get_ssdp = {
        "mock-domain": [
            {
                ssdp.ATTR_UPNP_DEVICE_TYPE: "Paulus",
                ssdp.ATTR_UPNP_MANUFACTURER: "Paulus",
            }
        ]
    }
    mock_init = await _async_run_mocked_scan(hass, mock_ssdp_response, mock_get_ssdp)

    assert not mock_init.mock_calls


async def test_invalid_characters(hass, aioclient_mock):
    """Test that we replace bad characters with placeholders."""
    aioclient_mock.get(
        "http://1.1.1.1",
        text="""
<root>
  <device>
    <deviceType>ABC</deviceType>
    <serialNumber>\xff\xff\xff\xff</serialNumber>
  </device>
</root>
    """,
    )

    mock_ssdp_response = {
        "st": "mock-st",
        "location": "http://1.1.1.1",
    }
    mock_get_ssdp = {
        "mock-domain": [
            {
                ssdp.ATTR_UPNP_DEVICE_TYPE: "ABC",
            }
        ]
    }

    mock_init = await _async_run_mocked_scan(hass, mock_ssdp_response, mock_get_ssdp)

    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_init.mock_calls[0][2]["context"] == {
        "source": config_entries.SOURCE_SSDP
    }
    assert mock_init.mock_calls[0][2]["data"] == {
        "ssdp_location": "http://1.1.1.1",
        "ssdp_st": "mock-st",
        "deviceType": "ABC",
        "serialNumber": "ÿÿÿÿ",
    }


@patch("homeassistant.components.ssdp.SSDPListener.async_start")
@patch("homeassistant.components.ssdp.SSDPListener.async_search")
async def test_start_stop_scanner(async_start_mock, async_search_mock, hass):
    """Test we start and stop the scanner."""
    assert await async_setup_component(hass, ssdp.DOMAIN, {ssdp.DOMAIN: {}})

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=200))
    await hass.async_block_till_done()
    assert async_start_mock.call_count == 1
    assert async_search_mock.call_count == 1

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=200))
    await hass.async_block_till_done()
    assert async_start_mock.call_count == 1
    assert async_search_mock.call_count == 1


async def test_unexpected_exception_while_fetching(hass, aioclient_mock, caplog):
    """Test unexpected exception while fetching."""
    aioclient_mock.get(
        "http://1.1.1.1",
        text="""
<root>
  <device>
    <deviceType>ABC</deviceType>
    <serialNumber>\xff\xff\xff\xff</serialNumber>
  </device>
</root>
    """,
    )
    mock_ssdp_response = {
        "st": "mock-st",
        "location": "http://1.1.1.1",
    }
    mock_get_ssdp = {
        "mock-domain": [
            {
                ssdp.ATTR_UPNP_DEVICE_TYPE: "ABC",
            }
        ]
    }

    with patch(
        "homeassistant.components.ssdp.descriptions.ElementTree.fromstring",
        side_effect=ValueError,
    ):
        mock_init = await _async_run_mocked_scan(
            hass, mock_ssdp_response, mock_get_ssdp
        )

    assert len(mock_init.mock_calls) == 0
    assert "Failed to fetch ssdp data from: http://1.1.1.1" in caplog.text

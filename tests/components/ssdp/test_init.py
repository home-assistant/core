"""Test the SSDP integration."""
import asyncio
from unittest.mock import patch, Mock

import aiohttp
import pytest

from homeassistant.generated import ssdp as gn_ssdp
from homeassistant.components import ssdp

from tests.common import mock_coro


async def test_scan_match_st(hass):
    """Test matching based on ST."""
    scanner = ssdp.Scanner(hass)

    with patch(
        "netdisco.ssdp.scan", return_value=[Mock(st="mock-st", location=None)]
    ), patch.dict(gn_ssdp.SSDP["st"], {"mock-st": ["mock-domain"]}), patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
        await scanner.async_scan(None)

    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_init.mock_calls[0][2]["context"] == {"source": "ssdp"}


async def test_scan_match_manufacturer(hass, aioclient_mock):
    """Test matching based on ST."""
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
    scanner = ssdp.Scanner(hass)

    with patch(
        "netdisco.ssdp.scan",
        return_value=[Mock(st="mock-st", location="http://1.1.1.1")],
    ), patch.dict(
        gn_ssdp.SSDP["manufacturer"], {"Paulus": ["mock-domain"]}
    ), patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
        await scanner.async_scan(None)

    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_init.mock_calls[0][2]["context"] == {"source": "ssdp"}


async def test_scan_match_device_type(hass, aioclient_mock):
    """Test matching based on ST."""
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
    scanner = ssdp.Scanner(hass)

    with patch(
        "netdisco.ssdp.scan",
        return_value=[Mock(st="mock-st", location="http://1.1.1.1")],
    ), patch.dict(
        gn_ssdp.SSDP["device_type"], {"Paulus": ["mock-domain"]}
    ), patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
        await scanner.async_scan(None)

    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_init.mock_calls[0][2]["context"] == {"source": "ssdp"}


@pytest.mark.parametrize("exc", [asyncio.TimeoutError, aiohttp.ClientError])
async def test_scan_description_fetch_fail(hass, aioclient_mock, exc):
    """Test failing to fetch description."""
    aioclient_mock.get("http://1.1.1.1", exc=exc)
    scanner = ssdp.Scanner(hass)

    with patch(
        "netdisco.ssdp.scan",
        return_value=[Mock(st="mock-st", location="http://1.1.1.1")],
    ):
        await scanner.async_scan(None)


async def test_scan_description_parse_fail(hass, aioclient_mock):
    """Test invalid XML."""
    aioclient_mock.get(
        "http://1.1.1.1",
        text="""
<root>INVALIDXML
    """,
    )
    scanner = ssdp.Scanner(hass)

    with patch(
        "netdisco.ssdp.scan",
        return_value=[Mock(st="mock-st", location="http://1.1.1.1")],
    ):
        await scanner.async_scan(None)

"""Test the SSDP integration."""
import asyncio
from unittest.mock import Mock, patch

import aiohttp
import pytest

from homeassistant.components import ssdp

from tests.common import mock_coro


async def test_scan_match_st(hass, caplog):
    """Test matching based on ST."""
    scanner = ssdp.Scanner(hass, {"mock-domain": [{"st": "mock-st"}]})

    async def _inject_entry(*args, **kwargs):
        scanner.async_store_entry(
            Mock(
                st="mock-st",
                location=None,
                values={"usn": "mock-usn", "server": "mock-server", "ext": ""},
            )
        )

    with patch(
        "homeassistant.components.ssdp.async_search",
        side_effect=_inject_entry,
    ), patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
        await scanner.async_scan(None)

    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_init.mock_calls[0][2]["context"] == {"source": "ssdp"}
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
    scanner = ssdp.Scanner(hass, {"mock-domain": [{key: "Paulus"}]})

    async def _inject_entry(*args, **kwargs):
        scanner.async_store_entry(
            Mock(st="mock-st", location="http://1.1.1.1", values={})
        )

    with patch(
        "homeassistant.components.ssdp.async_search",
        side_effect=_inject_entry,
    ), patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
        await scanner.async_scan(None)

    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_init.mock_calls[0][2]["context"] == {"source": "ssdp"}


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
    scanner = ssdp.Scanner(
        hass,
        {
            "mock-domain": [
                {
                    ssdp.ATTR_UPNP_DEVICE_TYPE: "Paulus",
                    ssdp.ATTR_UPNP_MANUFACTURER: "Paulus",
                }
            ]
        },
    )

    async def _inject_entry(*args, **kwargs):
        scanner.async_store_entry(
            Mock(st="mock-st", location="http://1.1.1.1", values={})
        )

    with patch(
        "homeassistant.components.ssdp.async_search",
        side_effect=_inject_entry,
    ), patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
        await scanner.async_scan(None)

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
    scanner = ssdp.Scanner(
        hass,
        {
            "mock-domain": [
                {
                    ssdp.ATTR_UPNP_DEVICE_TYPE: "Paulus",
                    ssdp.ATTR_UPNP_MANUFACTURER: "Not-Paulus",
                }
            ]
        },
    )

    async def _inject_entry(*args, **kwargs):
        scanner.async_store_entry(
            Mock(st="mock-st", location="http://1.1.1.1", values={})
        )

    with patch(
        "homeassistant.components.ssdp.async_search",
        side_effect=_inject_entry,
    ), patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
        await scanner.async_scan(None)

    assert not mock_init.mock_calls


@pytest.mark.parametrize("exc", [asyncio.TimeoutError, aiohttp.ClientError])
async def test_scan_description_fetch_fail(hass, aioclient_mock, exc):
    """Test failing to fetch description."""
    aioclient_mock.get("http://1.1.1.1", exc=exc)
    scanner = ssdp.Scanner(hass, {})

    async def _inject_entry(*args, **kwargs):
        scanner.async_store_entry(
            Mock(st="mock-st", location="http://1.1.1.1", values={})
        )

    with patch(
        "homeassistant.components.ssdp.async_search",
        side_effect=_inject_entry,
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
    scanner = ssdp.Scanner(hass, {})

    async def _inject_entry(*args, **kwargs):
        scanner.async_store_entry(
            Mock(st="mock-st", location="http://1.1.1.1", values={})
        )

    with patch(
        "homeassistant.components.ssdp.async_search",
        side_effect=_inject_entry,
    ):
        await scanner.async_scan(None)


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
    scanner = ssdp.Scanner(
        hass,
        {
            "mock-domain": [
                {
                    ssdp.ATTR_UPNP_DEVICE_TYPE: "ABC",
                }
            ]
        },
    )

    async def _inject_entry(*args, **kwargs):
        scanner.async_store_entry(
            Mock(st="mock-st", location="http://1.1.1.1", values={})
        )

    with patch(
        "homeassistant.components.ssdp.async_search",
        side_effect=_inject_entry,
    ), patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
        await scanner.async_scan(None)

    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_init.mock_calls[0][2]["context"] == {"source": "ssdp"}
    assert mock_init.mock_calls[0][2]["data"] == {
        "ssdp_location": "http://1.1.1.1",
        "ssdp_st": "mock-st",
        "deviceType": "ABC",
        "serialNumber": "ÿÿÿÿ",
    }

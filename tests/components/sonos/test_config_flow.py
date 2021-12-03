"""Test the sonos config flow."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant import config_entries, core
from homeassistant.components import zeroconf
from homeassistant.components.sonos.const import DATA_SONOS_DISCOVERY_MANAGER, DOMAIN


@patch("homeassistant.components.sonos.config_flow.soco.discover", return_value=True)
async def test_user_form(discover_mock: MagicMock, hass: core.HomeAssistant):
    """Test we get the user initiated form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None
    with patch(
        "homeassistant.components.sonos.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.sonos.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Sonos"
    assert result2["data"] == {}
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_form(hass: core.HomeAssistant):
    """Test we pass sonos devices to the discovery manager."""

    mock_manager = hass.data[DATA_SONOS_DISCOVERY_MANAGER] = MagicMock()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host="192.168.4.2",
            hostname="Sonos-aaa",
            name="Sonos-aaa@Living Room._sonos._tcp.local.",
            port=None,
            properties={"bootseq": "1234"},
            type="mock_type",
        ),
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.sonos.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.sonos.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Sonos"
    assert result2["data"] == {}

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_manager.mock_calls) == 2


async def test_zeroconf_sonos_v1(hass: core.HomeAssistant):
    """Test we pass sonos devices to the discovery manager with v1 firmware devices."""

    mock_manager = hass.data[DATA_SONOS_DISCOVERY_MANAGER] = MagicMock()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host="192.168.1.107",
            port=1443,
            hostname="sonos5CAAFDE47AC8.local.",
            type="_sonos._tcp.local.",
            name="Sonos-5CAAFDE47AC8._sonos._tcp.local.",
            properties={
                "_raw": {
                    "info": b"/api/v1/players/RINCON_5CAAFDE47AC801400/info",
                    "vers": b"1",
                    "protovers": b"1.18.9",
                },
                "info": "/api/v1/players/RINCON_5CAAFDE47AC801400/info",
                "vers": "1",
                "protovers": "1.18.9",
            },
        ),
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.sonos.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.sonos.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Sonos"
    assert result2["data"] == {}

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_manager.mock_calls) == 2


async def test_zeroconf_form_not_sonos(hass: core.HomeAssistant):
    """Test we abort on non-sonos devices."""
    mock_manager = hass.data[DATA_SONOS_DISCOVERY_MANAGER] = MagicMock()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host="192.168.4.2",
            hostname="not-aaa",
            name="mock_name",
            port=None,
            properties={"bootseq": "1234"},
            type="mock_type",
        ),
    )
    assert result["type"] == "abort"
    assert result["reason"] == "not_sonos_device"
    assert len(mock_manager.mock_calls) == 0

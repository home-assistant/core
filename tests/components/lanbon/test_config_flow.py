"""Tests for the LANBON integration config flow."""
from __future__ import annotations

from collections.abc import Generator
from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.lanbon.const import CONF_TOKEN, DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

HOST = "192.168.0.106"
PORT = 8765
TOKEN = "a" * 32
MAC = "DCDA0C3BC764"

INFO_ROOT = {
    "proto": 1,
    "mac": MAC.lower(),
    "name": "4gang Switch",
    "type_name": "4gang Switch",
    "sw_type": 224,
    "mesh_level": 1,
    "is_root": True,
    "port": PORT,
}


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[None]:
    """Prevent actual setup during config flow tests."""
    with patch(
        "homeassistant.components.lanbon.async_setup_entry",
        return_value=True,
    ):
        yield


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test user config flow success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.lanbon.config_flow.LanbonApi.async_get_info",
        new=AsyncMock(return_value=INFO_ROOT),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST, CONF_PORT: PORT, CONF_TOKEN: TOKEN},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "4gang Switch"
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_TOKEN] == TOKEN
    assert result["data"]["mac"] == MAC


async def test_user_invalid_auth(hass: HomeAssistant) -> None:
    """Test invalid token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(
        "homeassistant.components.lanbon.config_flow.LanbonApi.async_get_info",
        new=AsyncMock(side_effect=PermissionError("bad")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST, CONF_PORT: PORT, CONF_TOKEN: "bad"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test connection failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(
        "homeassistant.components.lanbon.config_flow.LanbonApi.async_get_info",
        new=AsyncMock(side_effect=OSError("down")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST, CONF_PORT: PORT, CONF_TOKEN: TOKEN},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_user_not_root(hass: HomeAssistant) -> None:
    """Test rejecting non-root panels."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    info = {**INFO_ROOT, "is_root": False}
    with patch(
        "homeassistant.components.lanbon.config_flow.LanbonApi.async_get_info",
        new=AsyncMock(return_value=info),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST, CONF_PORT: PORT, CONF_TOKEN: TOKEN},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "not_root"


async def test_zeroconf_flow(hass: HomeAssistant) -> None:
    """Test zeroconf discovery confirm."""
    discovery = ZeroconfServiceInfo(
        ip_address=ip_address(HOST),
        ip_addresses=[ip_address(HOST)],
        port=PORT,
        hostname="lanbon.local.",
        type="_lanbon._tcp.local.",
        name="4gang Switch._lanbon._tcp.local.",
        properties={
            "mac": MAC.lower(),
            "token": TOKEN,
            "type_name": "4gang Switch",
            "sw_type": "224",
        },
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    with patch(
        "homeassistant.components.lanbon.config_flow.LanbonApi.async_get_info",
        new=AsyncMock(return_value=INFO_ROOT),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: TOKEN}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["mac"] == MAC


async def test_abort_already_configured(hass: HomeAssistant) -> None:
    """Test abort when unique_id exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        data={CONF_HOST: HOST, CONF_PORT: PORT, CONF_TOKEN: TOKEN, "mac": MAC},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(
        "homeassistant.components.lanbon.config_flow.LanbonApi.async_get_info",
        new=AsyncMock(return_value=INFO_ROOT),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST, CONF_PORT: PORT, CONF_TOKEN: TOKEN},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

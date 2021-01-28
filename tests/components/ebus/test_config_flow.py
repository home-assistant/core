"""Tests for the EBUS config flow."""
from unittest.mock import patch

import pyebus

from homeassistant import data_entry_flow
from homeassistant.components.ebus.const import (
    API,
    CONF_CIRCUITINFOS,
    CONF_MSGDEFCODES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.typing import HomeAssistantType

from .const import HOST, INVALID_HOST, PORT


async def test_user_empty(hass: HomeAssistantType):
    """Test user config start."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=None
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_user_invalid_port(hass: HomeAssistantType):
    """Test user config with invalid port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: INVALID_HOST,
            CONF_PORT: PORT,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"host": "invalid_host"}


@patch("pyebus.Ebus.CONNECTOR", pyebus.DummyConnection)
@patch("pyebus.Ebus.DEFAULT_SCANINTERVAL", 0)
async def test_user_success(hass: HomeAssistantType):
    """Test user config with succeed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
        },
    )
    dummydata = pyebus.DummyData()
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == f"{HOST}:{PORT}"
    assert result["title"] == f"EBUS {HOST}:{PORT}"
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT
    assert result["data"][CONF_MSGDEFCODES] == dummydata.finddef
    assert result["data"][CONF_CIRCUITINFOS] == [
        {
            "address": 8,
            "circuit": "bai",
            "hwversion": "9602",
            "manufacturer": "Vaillant",
            "model": "BAI00",
            "swversion": "0204",
        },
        {
            "address": 35,
            "circuit": "cc",
            "hwversion": "6301",
            "manufacturer": "Vaillant",
            "model": "VR630",
            "swversion": "0500",
        },
        {
            "address": 38,
            "circuit": "hc",
            "hwversion": "6301",
            "manufacturer": "Vaillant",
            "model": "VR630",
            "swversion": "0500",
        },
        {
            "address": 37,
            "circuit": "hwc",
            "hwversion": "6301",
            "manufacturer": "Vaillant",
            "model": "VR630",
            "swversion": "0500",
        },
        {
            "address": 80,
            "circuit": "mc",
            "hwversion": "6301",
            "manufacturer": "Vaillant",
            "model": "VR630",
            "swversion": "0500",
        },
        {
            "address": 81,
            "circuit": "mc.3",
            "hwversion": "6301",
            "manufacturer": "Vaillant",
            "model": "VR630",
            "swversion": "0500",
        },
        {
            "address": 82,
            "circuit": "mc.4",
            "hwversion": "6301",
            "manufacturer": "Vaillant",
            "model": "MC2",
            "swversion": "0500",
        },
        {
            "address": 83,
            "circuit": "mc.5",
            "hwversion": "6301",
            "manufacturer": "Vaillant",
            "model": "MC2",
            "swversion": "0500",
        },
        {
            "address": 117,
            "circuit": "rcc",
            "hwversion": "6201",
            "manufacturer": "Vaillant",
            "model": "RC C",
            "swversion": "0508",
        },
        {
            "address": 245,
            "circuit": "rcc.3",
            "hwversion": "6201",
            "manufacturer": "Vaillant",
            "model": "RC C",
            "swversion": "0508",
        },
        {
            "address": 28,
            "circuit": "rcc.4",
            "hwversion": "6201",
            "manufacturer": "Vaillant",
            "model": "RC C",
            "swversion": "0508",
        },
        {
            "address": 60,
            "circuit": "rcc.5",
            "hwversion": "6201",
            "manufacturer": "Vaillant",
            "model": "RC C",
            "swversion": "0508",
        },
        {
            "address": 21,
            "circuit": "ui",
            "hwversion": "6201",
            "manufacturer": "Vaillant",
            "model": "UI",
            "swversion": "0508",
        },
    ]

    entries = hass.config_entries.async_entries()
    config_entry = entries[0]
    assert config_entry.unique_id == f"{HOST}:{PORT}"
    api = hass.data[DOMAIN][config_entry.entry_id][API]
    assert api.ebus.ident == f"{HOST}:{PORT}"
    assert api.ebus.host == HOST
    assert api.ebus.port == PORT

    # test abort on already configured
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

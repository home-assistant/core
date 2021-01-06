"""Tests for ZHA integration init."""

from unittest.mock import AsyncMock, patch

import pytest
from zigpy.config import CONF_DEVICE, CONF_DEVICE_PATH

from homeassistant.components.zha.core.const import (
    CONF_BAUDRATE,
    CONF_RADIO_TYPE,
    CONF_USB_PATH,
    DOMAIN,
)
from homeassistant.const import MAJOR_VERSION, MINOR_VERSION
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

DATA_RADIO_TYPE = "deconz"
DATA_PORT_PATH = "/dev/serial/by-id/FTDI_USB__-__Serial_Cable_12345678-if00-port0"


@pytest.fixture
def config_entry_v1(hass):
    """Config entry version 1 fixture."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_RADIO_TYPE: DATA_RADIO_TYPE, CONF_USB_PATH: DATA_PORT_PATH},
        version=1,
    )


@pytest.mark.parametrize("config", ({}, {DOMAIN: {}}))
@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
async def test_migration_from_v1_no_baudrate(hass, config_entry_v1, config):
    """Test migration of config entry from v1."""
    config_entry_v1.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, config)

    assert config_entry_v1.data[CONF_RADIO_TYPE] == DATA_RADIO_TYPE
    assert CONF_DEVICE in config_entry_v1.data
    assert config_entry_v1.data[CONF_DEVICE][CONF_DEVICE_PATH] == DATA_PORT_PATH
    assert CONF_BAUDRATE not in config_entry_v1.data[CONF_DEVICE]
    assert CONF_USB_PATH not in config_entry_v1.data
    assert config_entry_v1.version == 2


@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
async def test_migration_from_v1_with_baudrate(hass, config_entry_v1):
    """Test migration of config entry from v1 with baudrate in config."""
    config_entry_v1.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_BAUDRATE: 115200}})

    assert config_entry_v1.data[CONF_RADIO_TYPE] == DATA_RADIO_TYPE
    assert CONF_DEVICE in config_entry_v1.data
    assert config_entry_v1.data[CONF_DEVICE][CONF_DEVICE_PATH] == DATA_PORT_PATH
    assert CONF_USB_PATH not in config_entry_v1.data
    assert CONF_BAUDRATE in config_entry_v1.data[CONF_DEVICE]
    assert config_entry_v1.data[CONF_DEVICE][CONF_BAUDRATE] == 115200
    assert config_entry_v1.version == 2


@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
async def test_migration_from_v1_wrong_baudrate(hass, config_entry_v1):
    """Test migration of config entry from v1 with wrong baudrate."""
    config_entry_v1.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_BAUDRATE: 115222}})

    assert config_entry_v1.data[CONF_RADIO_TYPE] == DATA_RADIO_TYPE
    assert CONF_DEVICE in config_entry_v1.data
    assert config_entry_v1.data[CONF_DEVICE][CONF_DEVICE_PATH] == DATA_PORT_PATH
    assert CONF_USB_PATH not in config_entry_v1.data
    assert CONF_BAUDRATE not in config_entry_v1.data[CONF_DEVICE]
    assert config_entry_v1.version == 2


@pytest.mark.skipif(
    MAJOR_VERSION != 0 or (MAJOR_VERSION == 0 and MINOR_VERSION >= 112),
    reason="Not applicaable for this version",
)
@pytest.mark.parametrize(
    "zha_config",
    (
        {},
        {CONF_USB_PATH: "str"},
        {CONF_RADIO_TYPE: "ezsp"},
        {CONF_RADIO_TYPE: "ezsp", CONF_USB_PATH: "str"},
    ),
)
async def test_config_depreciation(hass, zha_config):
    """Test config option depreciation."""
    await async_setup_component(hass, "persistent_notification", {})

    with patch(
        "homeassistant.components.zha.async_setup", return_value=True
    ) as setup_mock:
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: zha_config})
        assert setup_mock.call_count == 1

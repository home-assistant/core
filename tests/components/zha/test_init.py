"""Tests for ZHA integration init."""

import pytest
from zigpy.config import CONF_DEVICE, CONF_DEVICE_PATH

import homeassistant.components.zha
from homeassistant.components.zha.core.const import (
    CONF_BAUDRATE,
    CONF_RADIO_TYPE,
    CONF_USB_PATH,
    DOMAIN,
)
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
async def test_migration_from_v1_no_baudrate(hass, config_entry_v1, config):
    """Test migration of config entry from v1."""
    assert await async_setup_component(hass, DOMAIN, config)
    await homeassistant.components.zha.async_migrate_entry(hass, config_entry_v1)

    assert config_entry_v1.data[CONF_RADIO_TYPE] == DATA_RADIO_TYPE
    assert CONF_DEVICE in config_entry_v1.data
    assert config_entry_v1.data[CONF_DEVICE][CONF_DEVICE_PATH] == DATA_PORT_PATH
    assert CONF_BAUDRATE not in config_entry_v1.data[CONF_DEVICE]
    assert CONF_USB_PATH not in config_entry_v1.data
    assert config_entry_v1.version == 2


async def test_migration_from_v1_with_baudrate(hass, config_entry_v1):
    """Test migration of config entry from v1 with baudrate in config."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_BAUDRATE: 115200}})
    await homeassistant.components.zha.async_migrate_entry(hass, config_entry_v1)

    assert config_entry_v1.data[CONF_RADIO_TYPE] == DATA_RADIO_TYPE
    assert CONF_DEVICE in config_entry_v1.data
    assert config_entry_v1.data[CONF_DEVICE][CONF_DEVICE_PATH] == DATA_PORT_PATH
    assert CONF_USB_PATH not in config_entry_v1.data
    assert CONF_BAUDRATE in config_entry_v1.data[CONF_DEVICE]
    assert config_entry_v1.data[CONF_DEVICE][CONF_BAUDRATE] == 115200
    assert config_entry_v1.version == 2


async def test_migration_from_v1_wrong_baudrate(hass, config_entry_v1):
    """Test migration of config entry from v1 with wrong baudrate."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_BAUDRATE: 115222}})
    await homeassistant.components.zha.async_migrate_entry(hass, config_entry_v1)

    assert config_entry_v1.data[CONF_RADIO_TYPE] == DATA_RADIO_TYPE
    assert CONF_DEVICE in config_entry_v1.data
    assert config_entry_v1.data[CONF_DEVICE][CONF_DEVICE_PATH] == DATA_PORT_PATH
    assert CONF_USB_PATH not in config_entry_v1.data
    assert CONF_BAUDRATE not in config_entry_v1.data[CONF_DEVICE]
    assert config_entry_v1.version == 2

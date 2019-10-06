"""Tests for the Neato init file."""
import pytest
from unittest.mock import patch

from homeassistant.components.neato.const import NEATO_DOMAIN, CONF_VENDOR
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

USERNAME = "myUsername"
PASSWORD = "myPassword"
VENDOR_NEATO = "neato"
VENDOR_VORWERK = "vorwerk"
VENDOR_INVALID = "invalid"

VALID_CONFIG = {
    CONF_USERNAME: USERNAME,
    CONF_PASSWORD: PASSWORD,
    CONF_VENDOR: VENDOR_NEATO,
}

INVALID_CONFIG = {
    CONF_USERNAME: USERNAME,
    CONF_PASSWORD: PASSWORD,
    CONF_VENDOR: VENDOR_INVALID,
}


@pytest.fixture(name="account")
def mock_controller_login():
    """Mock a successful login."""
    with patch("pybotvac.Account", return_value=True):
        yield


async def test_no_config_entry(hass):
    """There is nothing in configuration.yaml."""
    res = await async_setup_component(hass, NEATO_DOMAIN, {})
    assert res is True


async def test_config_entries_in_sync(hass, account):
    """The config entry and configuration.yaml are in sync."""
    MockConfigEntry(domain=NEATO_DOMAIN, data=VALID_CONFIG).add_to_hass(hass)

    assert hass.config_entries.async_entries(NEATO_DOMAIN)
    assert await async_setup_component(hass, NEATO_DOMAIN, {NEATO_DOMAIN: VALID_CONFIG})
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(NEATO_DOMAIN)
    assert entries
    assert entries[0].data[CONF_USERNAME] == USERNAME
    assert entries[0].data[CONF_PASSWORD] == PASSWORD
    assert entries[0].data[CONF_VENDOR] == VENDOR_NEATO


async def test_config_entries_not_in_sync(hass, account):
    """The config entry and configuration.yaml are not in sync."""
    MockConfigEntry(domain=NEATO_DOMAIN, data=INVALID_CONFIG).add_to_hass(hass)

    assert hass.config_entries.async_entries(NEATO_DOMAIN)
    assert await async_setup_component(hass, NEATO_DOMAIN, {NEATO_DOMAIN: VALID_CONFIG})
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(NEATO_DOMAIN)
    assert entries
    assert entries[0].data[CONF_USERNAME] == USERNAME
    assert entries[0].data[CONF_PASSWORD] == PASSWORD
    assert entries[0].data[CONF_VENDOR] == VENDOR_NEATO

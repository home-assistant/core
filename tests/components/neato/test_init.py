"""Tests for the Neato init file."""
from pybotvac.exceptions import NeatoLoginException
import pytest

from homeassistant.components.neato.const import CONF_VENDOR, NEATO_DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
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

DIFFERENT_CONFIG = {
    CONF_USERNAME: "anotherUsername",
    CONF_PASSWORD: "anotherPassword",
    CONF_VENDOR: VENDOR_VORWERK,
}

INVALID_CONFIG = {
    CONF_USERNAME: USERNAME,
    CONF_PASSWORD: PASSWORD,
    CONF_VENDOR: VENDOR_INVALID,
}


@pytest.fixture(name="config_flow")
def mock_config_flow_login():
    """Mock a successful login."""
    with patch("homeassistant.components.neato.config_flow.Account", return_value=True):
        yield


@pytest.fixture(name="hub")
def mock_controller_login():
    """Mock a successful login."""
    with patch("homeassistant.components.neato.Account", return_value=True):
        yield


async def test_no_config_entry(hass):
    """There is nothing in configuration.yaml."""
    res = await async_setup_component(hass, NEATO_DOMAIN, {})
    assert res is True


async def test_create_valid_config_entry(hass, config_flow, hub):
    """There is something in configuration.yaml."""
    assert hass.config_entries.async_entries(NEATO_DOMAIN) == []
    assert await async_setup_component(hass, NEATO_DOMAIN, {NEATO_DOMAIN: VALID_CONFIG})
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(NEATO_DOMAIN)
    assert entries
    assert entries[0].data[CONF_USERNAME] == USERNAME
    assert entries[0].data[CONF_PASSWORD] == PASSWORD
    assert entries[0].data[CONF_VENDOR] == VENDOR_NEATO


async def test_config_entries_in_sync(hass, hub):
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


async def test_config_entries_not_in_sync(hass, config_flow, hub):
    """The config entry and configuration.yaml are not in sync."""
    MockConfigEntry(domain=NEATO_DOMAIN, data=DIFFERENT_CONFIG).add_to_hass(hass)

    assert hass.config_entries.async_entries(NEATO_DOMAIN)
    assert await async_setup_component(hass, NEATO_DOMAIN, {NEATO_DOMAIN: VALID_CONFIG})
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(NEATO_DOMAIN)
    assert entries
    assert entries[0].data[CONF_USERNAME] == USERNAME
    assert entries[0].data[CONF_PASSWORD] == PASSWORD
    assert entries[0].data[CONF_VENDOR] == VENDOR_NEATO


async def test_config_entries_not_in_sync_error(hass):
    """The config entry and configuration.yaml are not in sync, the new configuration is wrong."""
    MockConfigEntry(domain=NEATO_DOMAIN, data=VALID_CONFIG).add_to_hass(hass)

    assert hass.config_entries.async_entries(NEATO_DOMAIN)
    with patch(
        "homeassistant.components.neato.config_flow.Account",
        side_effect=NeatoLoginException(),
    ):
        assert not await async_setup_component(
            hass, NEATO_DOMAIN, {NEATO_DOMAIN: DIFFERENT_CONFIG}
        )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(NEATO_DOMAIN)
    assert entries
    assert entries[0].data[CONF_USERNAME] == USERNAME
    assert entries[0].data[CONF_PASSWORD] == PASSWORD
    assert entries[0].data[CONF_VENDOR] == VENDOR_NEATO

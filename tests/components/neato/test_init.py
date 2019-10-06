"""Tests for the Neato init file."""
import pytest
from unittest.mock import patch

from homeassistant.components.neato import NeatoHub
from homeassistant.components.neato.const import (
    CONF_VENDOR,
    NEATO_DOMAIN,
    NEATO_ROBOTS,
    NEATO_MAP_DATA,
    NEATO_PERSISTENT_MAPS,
)
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


class MockAccount:
    """This class behaves like Account from pybotvac."""

    # TODO: Is it possible to use a fixture here, that makes this class more flexible?

    robots = "MyRobots"
    maps = "MyMaps"
    persistent_maps = "MyPersistentMaps"

    def __init__(self, email, password, vendor):
        """Initialize the mocked object."""
        pass

    @staticmethod
    def get_map_image(url):
        """Return a hard coded string."""
        return "MyMapImage"


@pytest.fixture(name="account")
def mock_controller_login():
    """Mock a successful login."""
    with patch("pybotvac.Account", return_value=MockAccount):
        yield


async def test_no_config_entry(hass):
    """There is nothing in configuration.yaml."""
    res = await async_setup_component(hass, NEATO_DOMAIN, {})
    assert res is True


async def test_create_valid_config_entry(hass, account):
    """There is something in configuration.yaml."""
    assert hass.config_entries.async_entries(NEATO_DOMAIN) == []
    assert await async_setup_component(hass, NEATO_DOMAIN, {NEATO_DOMAIN: VALID_CONFIG})
    entries = hass.config_entries.async_entries(NEATO_DOMAIN)
    await hass.async_block_till_done()

    assert entries
    assert entries[0].data[CONF_USERNAME] == USERNAME
    assert entries[0].data[CONF_PASSWORD] == PASSWORD
    assert entries[0].data[CONF_VENDOR] == VENDOR_NEATO


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


async def test_setup_entry(hass, account):
    """Test setup of components."""
    # TODO: write test
    pass


async def test_unload_entry(hass, account):
    """Test unload of components."""
    # TODO: write test
    pass


async def test_fetch_successful(hass, account):
    """Test successful fetch after login."""
    from pybotvac import Account, Vorwerk

    hub = NeatoHub(hass, VALID_CONFIG, Account, Vorwerk)
    assert hub.logged_in
    assert hass.data[NEATO_ROBOTS] == "MyRobots"
    assert hass.data[NEATO_PERSISTENT_MAPS] == "MyPersistentMaps"
    assert hass.data[NEATO_MAP_DATA] == "MyMaps"


async def test_fetch_update_robots(hass, account):
    """Test successful fetch in update method."""
    from pybotvac import Account, Neato

    hub = NeatoHub(hass, VALID_CONFIG, Account, Neato)
    assert hub.logged_in
    assert hass.data[NEATO_ROBOTS] == "MyRobots"
    assert hass.data[NEATO_PERSISTENT_MAPS] == "MyPersistentMaps"
    assert hass.data[NEATO_MAP_DATA] == "MyMaps"

    acc = hub.my_neato
    acc.robots = "NewRobots"
    acc.maps = "NewMaps"
    acc.persistent_maps = "NewPersistentMaps"
    hub.update_robots()

    assert hass.data[NEATO_ROBOTS] == "NewRobots"
    assert hass.data[NEATO_PERSISTENT_MAPS] == "NewPersistentMaps"
    assert hass.data[NEATO_MAP_DATA] == "NewMaps"


async def test_fetch_unsuccessful(hass):
    """Test unsuccessful fetch."""
    from requests.exceptions import HTTPError
    from pybotvac import Account, Vorwerk

    with patch("pybotvac.Account", side_effect=HTTPError()):
        hub = NeatoHub(hass, VALID_CONFIG, Account, Vorwerk)

    assert not hub.logged_in
    assert NEATO_ROBOTS not in hass.data
    assert NEATO_PERSISTENT_MAPS not in hass.data
    assert NEATO_MAP_DATA not in hass.data


async def test_download_map(hass, account):
    """Test successful download of map."""
    from pybotvac import Account, Neato

    hub = NeatoHub(hass, VALID_CONFIG, Account, Neato)
    assert hub.download_map("SomeTestURL") == "MyMapImage"

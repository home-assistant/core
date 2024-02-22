"""Test configuration and mocks for LCN component."""
import json
from unittest.mock import AsyncMock, patch

import pypck
from pypck.connection import PchkConnectionManager
import pypck.module
from pypck.module import GroupConnection, ModuleConnection
import pytest

from homeassistant.components.lcn.const import DOMAIN
from homeassistant.components.lcn.helpers import generate_unique_id
from homeassistant.const import CONF_HOST
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_mock_service, load_fixture


class MockModuleConnection(ModuleConnection):
    """Fake a LCN module connection."""

    status_request_handler = AsyncMock()
    activate_status_request_handler = AsyncMock()
    cancel_status_request_handler = AsyncMock()
    request_name = AsyncMock(return_value="TestModule")
    send_command = AsyncMock(return_value=True)

    def __init__(self, *args, **kwargs):
        """Construct ModuleConnection instance."""
        super().__init__(*args, **kwargs)
        self.serials_request_handler.serial_known.set()


class MockGroupConnection(GroupConnection):
    """Fake a LCN group connection."""

    send_command = AsyncMock(return_value=True)


class MockPchkConnectionManager(PchkConnectionManager):
    """Fake connection handler."""

    async def async_connect(self, timeout=30):
        """Mock establishing a connection to PCHK."""
        self.authentication_completed_future.set_result(True)
        self.license_error_future.set_result(True)
        self.segment_scan_completed_event.set()

    async def async_close(self):
        """Mock closing a connection to PCHK."""

    @patch.object(pypck.connection, "ModuleConnection", MockModuleConnection)
    @patch.object(pypck.connection, "GroupConnection", MockGroupConnection)
    def get_address_conn(self, addr, request_serials=False):
        """Get LCN address connection."""
        return super().get_address_conn(addr, request_serials)

    send_command = AsyncMock()


def create_config_entry(name):
    """Set up config entries with configuration data."""
    fixture_filename = f"lcn/config_entry_{name}.json"
    entry_data = json.loads(load_fixture(fixture_filename))
    options = {}

    title = entry_data[CONF_HOST]
    unique_id = fixture_filename
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=title,
        unique_id=unique_id,
        data=entry_data,
        options=options,
    )
    return entry


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture(name="entry")
def create_config_entry_pchk():
    """Return one specific config entry."""
    return create_config_entry("pchk")


@pytest.fixture(name="entry2")
def create_config_entry_myhome():
    """Return one specific config entry."""
    return create_config_entry("myhome")


@pytest.fixture(name="lcn_connection")
async def init_integration(hass, entry):
    """Set up the LCN integration in Home Assistant."""
    lcn_connection = None

    def lcn_connection_factory(*args, **kwargs):
        nonlocal lcn_connection
        lcn_connection = MockPchkConnectionManager(*args, **kwargs)
        return lcn_connection

    entry.add_to_hass(hass)
    with patch(
        "pypck.connection.PchkConnectionManager",
        side_effect=lcn_connection_factory,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield lcn_connection


async def setup_component(hass):
    """Set up the LCN component."""
    fixture_filename = "lcn/config.json"
    config_data = json.loads(load_fixture(fixture_filename))

    await async_setup_component(hass, DOMAIN, config_data)
    await hass.async_block_till_done()


def get_device(hass, entry, address):
    """Get LCN device for specified address."""
    device_registry = dr.async_get(hass)
    identifiers = {(DOMAIN, generate_unique_id(entry.entry_id, address))}
    device = device_registry.async_get_device(identifiers=identifiers)
    assert device
    return device

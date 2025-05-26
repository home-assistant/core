"""Test configuration and mocks for LCN component."""

import json
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pypck
import pypck.module
from pypck.module import GroupConnection, ModuleConnection
import pytest

from homeassistant.components.lcn import PchkConnectionManager
from homeassistant.components.lcn.config_flow import LcnFlowHandler
from homeassistant.components.lcn.const import DOMAIN
from homeassistant.components.lcn.helpers import AddressType, generate_unique_id
from homeassistant.const import CONF_ADDRESS, CONF_DEVICES, CONF_ENTITIES, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry, load_fixture

LATEST_CONFIG_ENTRY_VERSION = (LcnFlowHandler.VERSION, LcnFlowHandler.MINOR_VERSION)


class MockModuleConnection(ModuleConnection):
    """Fake a LCN module connection."""

    status_request_handler = AsyncMock()
    activate_status_request_handler = AsyncMock()
    cancel_status_request_handler = AsyncMock()
    request_name = AsyncMock(return_value="TestModule")
    send_command = AsyncMock(return_value=True)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Construct ModuleConnection instance."""
        super().__init__(*args, **kwargs)
        self.serials_request_handler.serial_known.set()


class MockGroupConnection(GroupConnection):
    """Fake a LCN group connection."""

    send_command = AsyncMock(return_value=True)


class MockPchkConnectionManager(PchkConnectionManager):
    """Fake connection handler."""

    async def async_connect(self, timeout: int = 30) -> None:
        """Mock establishing a connection to PCHK."""
        self.authentication_completed_future.set_result(True)
        self.license_error_future.set_result(True)
        self.segment_scan_completed_event.set()

    async def async_close(self) -> None:
        """Mock closing a connection to PCHK."""

    def get_address_conn(self, addr, request_serials=False):
        """Get LCN address connection."""
        return super().get_address_conn(addr, request_serials)

    @patch.object(pypck.connection, "ModuleConnection", MockModuleConnection)
    def get_module_conn(self, addr, request_serials=False):
        """Get LCN module connection."""
        return super().get_module_conn(addr, request_serials)

    @patch.object(pypck.connection, "GroupConnection", MockGroupConnection)
    def get_group_conn(self, addr):
        """Get LCN group connection."""
        return super().get_group_conn(addr)

    scan_modules = AsyncMock()
    send_command = AsyncMock()


def create_config_entry(
    name: str, version: tuple[int, int] = LATEST_CONFIG_ENTRY_VERSION
) -> MockConfigEntry:
    """Set up config entries with configuration data."""
    fixture_filename = f"lcn/config_entry_{name}.json"
    entry_data = json.loads(load_fixture(fixture_filename))
    for device in entry_data[CONF_DEVICES]:
        device[CONF_ADDRESS] = tuple(device[CONF_ADDRESS])
    for entity in entry_data[CONF_ENTITIES]:
        entity[CONF_ADDRESS] = tuple(entity[CONF_ADDRESS])

    options = {}

    title = entry_data[CONF_HOST]
    return MockConfigEntry(
        entry_id=fixture_filename.replace(".", "_"),
        domain=DOMAIN,
        title=title,
        data=entry_data,
        options=options,
        version=version[0],
        minor_version=version[1],
    )


@pytest.fixture(name="entry")
def create_config_entry_pchk() -> MockConfigEntry:
    """Return one specific config entry."""
    return create_config_entry("pchk")


@pytest.fixture(name="entry2")
def create_config_entry_myhome() -> MockConfigEntry:
    """Return one specific config entry."""
    return create_config_entry("myhome")


async def init_integration(
    hass: HomeAssistant, entry: MockConfigEntry
) -> MockPchkConnectionManager:
    """Set up the LCN integration in Home Assistant."""
    hass.http = Mock()  # needs to be mocked as hass.http.register_static_path is called when registering the frontend
    lcn_connection = None

    def lcn_connection_factory(*args, **kwargs):
        nonlocal lcn_connection
        lcn_connection = MockPchkConnectionManager(*args, **kwargs)
        return lcn_connection

    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.lcn.PchkConnectionManager",
        side_effect=lcn_connection_factory,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return lcn_connection


def get_device(
    hass: HomeAssistant, entry: MockConfigEntry, address: AddressType
) -> dr.DeviceEntry:
    """Get LCN device for specified address."""
    device_registry = dr.async_get(hass)
    identifiers = {(DOMAIN, generate_unique_id(entry.entry_id, address))}
    device = device_registry.async_get_device(identifiers=identifiers)
    assert device
    return device

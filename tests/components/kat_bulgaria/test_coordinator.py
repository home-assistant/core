"""Coordinator."""

from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers.update_coordinator import Awaitable, Callable

from . import EGN_VALID, LICENSE_VALID

from tests.common import MockConfigEntry


# region Integration Setup
async def test_coordinator_update_nodata(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    client: MagicMock,
    katclient_get_obligations_success_none,
) -> None:
    """Test that the coordinator can update."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED


async def test_coordinator_usernotfoundonline(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    client: MagicMock,
    katclient_get_obligations_usernotfoundonline,
) -> None:
    """Test that the coordinator can update."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.SETUP_ERROR


async def test_coordinator_api_timeout(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    client: MagicMock,
    katclient_get_obligations_api_timeout,
) -> None:
    """Test that the coordinator can update."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_coordinator_api_toomanyrequests(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    client: MagicMock,
    katclient_get_obligations_api_toomanyrequests,
) -> None:
    """Test that the coordinator can update."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_coordinator_api_invaliddata(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    client: MagicMock,
    katclient_get_obligations_api_errorreadingdata,
) -> None:
    """Test that the coordinator can update."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_coordinator_api_invalidschema(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    client: MagicMock,
    katclient_get_obligations_api_invalidschema,
) -> None:
    """Test that the coordinator can update."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_coordinator_api_unknownerror(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    client: MagicMock,
    katclient_get_obligations_api_unknownerror,
) -> None:
    """Test that the coordinator can update."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.SETUP_RETRY


# endregion


# region Fetch data


async def test_coordinator_update(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    client_fine_served: MagicMock,
    katclient_get_obligations_success_none,
) -> None:
    """Test that the coordinator can update."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client_fine_served)
    assert config_entry.state == ConfigEntryState.LOADED
    assert client_fine_served.get_obligations.call_count == 1
    assert client_fine_served.get_obligations.call_args[0] == (EGN_VALID, LICENSE_VALID)


# endregion

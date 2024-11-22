"""Common tradfri test fixtures."""

from __future__ import annotations

from collections.abc import Callable, Generator
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytradfri.command import Command
from pytradfri.const import ATTR_FIRMWARE_VERSION, ATTR_GATEWAY_ID
from pytradfri.device import Device
from pytradfri.gateway import Gateway

from homeassistant.components.tradfri.const import DOMAIN

from . import GATEWAY_ID, TRADFRI_PATH
from .common import CommandStore

from tests.common import load_fixture


@pytest.fixture
def mock_entry_setup() -> Generator[AsyncMock]:
    """Mock entry setup."""
    with patch(f"{TRADFRI_PATH}.async_setup_entry") as mock_setup:
        mock_setup.return_value = True
        yield mock_setup


@pytest.fixture(name="mock_gateway", autouse=True)
def mock_gateway_fixture(command_store: CommandStore) -> Gateway:
    """Mock a Tradfri gateway."""
    gateway = Gateway()
    command_store.register_response(
        gateway.get_gateway_info(),
        {ATTR_GATEWAY_ID: GATEWAY_ID, ATTR_FIRMWARE_VERSION: "1.2.1234"},
    )
    command_store.register_response(
        gateway.get_devices(),
        [],
    )
    return gateway


@pytest.fixture(name="command_store", autouse=True)
def command_store_fixture() -> CommandStore:
    """Store commands and command responses for the API."""
    return CommandStore([], {})


@pytest.fixture(name="mock_api")
def mock_api_fixture(
    command_store: CommandStore,
) -> Callable[[Command | list[Command], float | None], Any | None]:
    """Mock api."""

    async def api(
        command: Command | list[Command], timeout: float | None = None
    ) -> Any | None:
        """Mock api function."""
        if isinstance(command, list):
            result = []
            for cmd in command:
                command_store.sent_commands.append(cmd)
                result.append(command_store.process_command(cmd))
            return result

        command_store.sent_commands.append(command)
        return command_store.process_command(command)

    return api


@pytest.fixture(autouse=True)
def mock_api_factory(
    mock_api: Callable[[Command | list[Command], float | None], Any | None],
) -> Generator[MagicMock]:
    """Mock pytradfri api factory."""
    with patch(f"{TRADFRI_PATH}.APIFactory", autospec=True) as factory_class:
        factory = factory_class.return_value
        factory_class.init.return_value = factory
        factory.request = mock_api
        yield factory


@pytest.fixture
def device(
    command_store: CommandStore, mock_gateway: Gateway, request: pytest.FixtureRequest
) -> Device:
    """Return a device."""
    device_response: dict[str, Any] = json.loads(request.getfixturevalue(request.param))
    device = Device(device_response)
    command_store.register_device(mock_gateway, device.raw)
    return device


@pytest.fixture(scope="package")
def air_purifier() -> str:
    """Return an air purifier response."""
    return load_fixture("air_purifier.json", DOMAIN)


@pytest.fixture(scope="package")
def blind() -> str:
    """Return a blind response."""
    return load_fixture("blind.json", DOMAIN)

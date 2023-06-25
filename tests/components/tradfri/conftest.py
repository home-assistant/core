"""Common tradfri test fixtures."""
from __future__ import annotations

from collections.abc import Generator
import json
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from pytradfri.device import Device
from pytradfri.device.air_purifier import AirPurifier
from pytradfri.device.blind import Blind

from homeassistant.components.tradfri.const import DOMAIN

from . import GATEWAY_ID, TRADFRI_PATH

from tests.common import load_fixture


@pytest.fixture
def mock_gateway_info():
    """Mock get_gateway_info."""
    with patch(f"{TRADFRI_PATH}.config_flow.get_gateway_info") as gateway_info:
        yield gateway_info


@pytest.fixture
def mock_entry_setup():
    """Mock entry setup."""
    with patch(f"{TRADFRI_PATH}.async_setup_entry") as mock_setup:
        mock_setup.return_value = True
        yield mock_setup


@pytest.fixture(name="mock_gateway")
def mock_gateway_fixture():
    """Mock a Tradfri gateway."""

    def get_devices():
        """Return mock devices."""
        return gateway.mock_devices

    def get_groups():
        """Return mock groups."""
        return gateway.mock_groups

    gateway_info = Mock(id=GATEWAY_ID, firmware_version="1.2.1234")

    def get_gateway_info():
        """Return mock gateway info."""
        return gateway_info

    gateway = Mock(
        get_devices=get_devices,
        get_groups=get_groups,
        get_gateway_info=get_gateway_info,
        mock_commands=[],
        mock_devices=[],
        mock_groups=[],
        mock_responses=[],
    )
    with patch(f"{TRADFRI_PATH}.Gateway", return_value=gateway), patch(
        f"{TRADFRI_PATH}.config_flow.Gateway", return_value=gateway
    ):
        yield gateway


@pytest.fixture(name="mock_api")
def mock_api_fixture(mock_gateway):
    """Mock api."""

    async def api(command, timeout=None):
        """Mock api function."""
        # Store the data for "real" command objects.
        if hasattr(command, "_data") and not isinstance(command, Mock):
            mock_gateway.mock_responses.append(command._data)
            mock_gateway.mock_commands.append(command)
        return command

    return api


@pytest.fixture
def mock_api_factory(mock_api) -> Generator[MagicMock, None, None]:
    """Mock pytradfri api factory."""
    with patch(f"{TRADFRI_PATH}.APIFactory", autospec=True) as factory:
        factory.init.return_value = factory.return_value
        factory.return_value.request = mock_api
        yield factory.return_value


@pytest.fixture(scope="session")
def air_purifier_response() -> dict[str, Any]:
    """Return an air purifier response."""
    return json.loads(load_fixture("air_purifier.json", DOMAIN))


@pytest.fixture
def air_purifier(air_purifier_response: dict[str, Any]) -> AirPurifier:
    """Return air purifier."""
    device = Device(air_purifier_response)
    air_purifier_control = device.air_purifier_control
    assert air_purifier_control
    return air_purifier_control.air_purifiers[0]


@pytest.fixture(scope="session")
def blind_response() -> dict[str, Any]:
    """Return a blind response."""
    return json.loads(load_fixture("blind.json", DOMAIN))


@pytest.fixture
def blind(blind_response: dict[str, Any]) -> Blind:
    """Return blind."""
    device = Device(blind_response)
    blind_control = device.blind_control
    assert blind_control
    return blind_control.blinds[0]

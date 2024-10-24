"""Common fixtures for the viam tests."""

import asyncio
from collections.abc import Generator
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from viam.app.viam_client import ViamClient


@dataclass
class MockLocation:
    """Fake location for testing."""

    id: str = "13"
    name: str = "home"


@dataclass
class MockRobot:
    """Fake robot for testing."""

    id: str = "1234"
    name: str = "test"


def async_return(result):
    """Allow async return value with MagicMock."""

    future = asyncio.Future()
    future.set_result(result)
    return future


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.viam.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="mock_viam_client")
def mock_viam_client_fixture() -> Generator[tuple[MagicMock, MockRobot]]:
    """Override ViamClient from Viam SDK."""
    with (
        patch("viam.app.viam_client.ViamClient") as MockClient,
        patch.object(ViamClient, "create_from_dial_options") as mock_create_client,
    ):
        instance: MagicMock = MockClient.return_value
        mock_create_client.return_value = instance

        mock_location = MockLocation()
        mock_robot = MockRobot()
        instance.app_client.list_locations.return_value = async_return([mock_location])
        instance.app_client.get_location.return_value = async_return(mock_location)
        instance.app_client.list_robots.return_value = async_return([mock_robot])
        yield instance, mock_robot

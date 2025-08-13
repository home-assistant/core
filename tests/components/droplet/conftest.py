"""Common fixtures for the Droplet tests."""

from collections.abc import Generator
from enum import Enum, auto
import json
from unittest.mock import MagicMock, patch

import aiohttp
import pytest

from homeassistant.components.droplet.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.2"},
        unique_id="Droplet-1234",
    )


class MockClientBehaviors(Enum):
    """Options for a mocked WS client."""

    GOOD = auto()
    FAIL_OPEN = auto()
    NO_DEVICE_ID = auto()


class MockWSConnection:
    """Mock a websocket connection."""

    def __init__(self, behavior) -> None:
        """Initialize mock websocket connection."""
        self.action = behavior
        self.closed = False

    async def receive(self, timeout):
        """Mock receiving a message."""
        match self.action:
            case MockClientBehaviors.GOOD | MockClientBehaviors.NO_DEVICE_ID:
                return aiohttp.WSMessage(
                    aiohttp.WSMsgType.TEXT,
                    data=json.dumps({"flow": "1.01"}),
                    extra=None,
                )
            case MockClientBehaviors.FAIL_OPEN:
                return aiohttp.WSMessage(aiohttp.WSMsgType.CLOSED, data="", extra=None)

    async def receive_json(self, timeout):
        """Mock the receive_json websockets function."""
        match self.action:
            case MockClientBehaviors.GOOD:
                return {"ids": "Droplet-1234"}
            case _:
                raise json.JSONDecodeError("error", "", 0)

    async def close(self) -> bool:
        """Mock closing websocket."""
        self.closed = True
        return True


def mock_try_connect(behavior):
    """Return a mocked websocket connection."""
    return patch(
        "pydroplet.droplet.DropletConnection.get_client",
        return_value=MockWSConnection(behavior),
    )


@pytest.fixture
def mock_droplet() -> Generator[MagicMock]:
    """Return a mocked Droplet client."""
    with patch("pydroplet.droplet.Droplet", autospec=True) as droplet_mock:
        droplet = droplet_mock.return_value
        yield droplet


def mock_setup():
    """Mock setup function."""
    return True


@pytest.fixture
def mock_coordinator_setup():
    """Mock the droplet coordinator's setup."""
    with patch(
        "homeassistant.components.droplet.coordinator.DropletDataCoordinator.setup",
        new_callable=mock_setup,
    ) as coordinator_mock:
        yield coordinator_mock

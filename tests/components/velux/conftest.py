"""Fixtures for the Velbus tests."""
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pyvlx.config import Config
from pyvlx.node import Node
from pyvlx.opening_device import Blind, OpeningDevice, Window
from pyvlx.scene import Scene

from homeassistant.components.velux.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import HOST, PASSWORD

from tests.common import MockConfigEntry


class TestPyVLX:
    """Pyvlx mock class."""

    def __init__(self, host, password, *args: Any, **kwargs: Any) -> None:
        """Initialize pyvlx mock."""
        self.nodes: list[Node] = []
        self.scenes: list[Scene] = []
        self.config: Config = Config(pyvlx=self, host=host, password=password)
        self.version = "software test version"
        self.klf200 = AsyncMock()
        self.heartbeat = AsyncMock()
        self.connection = AsyncMock()
        self.reboot_initiated: bool = False
        self.disconnected: bool = False

    __test__ = False

    async def connect(self) -> None:
        """Simulate pyvlx connect function."""
        return

    async def load_nodes(self) -> None:
        """Load test nodes."""
        self.nodes.append(
            OpeningDevice(
                pyvlx=self, node_id=1, name="Cover 1", serial_number="Cover1_serial"
            )
        )
        self.nodes.append(
            Blind(pyvlx=self, node_id=2, name="Blind 2", serial_number="Cover2_serial")
        )
        self.nodes.append(
            Window(
                pyvlx=self, node_id=3, name="Window 3", serial_number="Cover3_serial"
            )
        )
        return

    async def load_scenes(self) -> None:
        """Load test scenes."""
        self.scenes.append(Scene(pyvlx=self, scene_id=1, name="Test scene 1"))
        self.scenes.append(Scene(pyvlx=self, scene_id=2, name="Test scene 2"))
        return

    async def reboot_gateway(self) -> None:
        """Simulate a gateway reboot."""
        self.reboot_initiated = True
        return

    async def disconnect(self) -> None:
        """Simulate a gateway reboot."""
        self.disconnected = True
        return


@pytest.fixture(name="pyvlx")
def mock_pyvlx() -> Generator[TestPyVLX, None, None]:
    """Mock a successful velux gateway."""
    with patch("homeassistant.components.velux.PyVLX", spec=TestPyVLX) as pyvlx:
        yield pyvlx


@pytest.fixture(name="config_entry")
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create and register mock config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PASSWORD: PASSWORD},
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture(name="config_type")
def config_type(hass: HomeAssistant) -> ConfigType:
    """Create and register mock config entry."""
    config_type = ConfigType(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PASSWORD: PASSWORD},
    )
    return config_type

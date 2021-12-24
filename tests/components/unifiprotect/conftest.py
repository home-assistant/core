"""Fixtures and test data for UniFi Protect methods."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from pyunifiprotect.data.types import Version

from homeassistant.components.unifiprotect.const import MIN_REQUIRED_PROTECT_V

MAC_ADDR = "aa:bb:cc:dd:ee:ff"


@dataclass
class MockNvrData:
    """Mock for NVR."""

    version: Version
    mac: str
    name: str
    id: str


@dataclass
class MockBootstrap:
    """Mock for Bootstrap."""

    nvr: MockNvrData
    cameras: dict[str, Any]
    lights: dict[str, Any]
    sensors: dict[str, Any]
    viewers: dict[str, Any]


MOCK_NVR_DATA = MockNvrData(
    version=MIN_REQUIRED_PROTECT_V, mac=MAC_ADDR, name="UnifiProtect", id="test_id"
)
MOCK_OLD_NVR_DATA = MockNvrData(
    version=Version("1.19.0"), mac=MAC_ADDR, name="UnifiProtect", id="test_id"
)

MOCK_BOOTSTRAP = MockBootstrap(
    nvr=MOCK_NVR_DATA, cameras={}, lights={}, sensors={}, viewers={}
)


@pytest.fixture
def mock_client():
    """Mock ProtectApiClient for testing."""
    client = Mock()
    client.bootstrap = MOCK_BOOTSTRAP

    client.get_nvr = AsyncMock(return_value=MOCK_NVR_DATA)
    client.update = AsyncMock(return_value=MOCK_BOOTSTRAP)
    client.async_disconnect_ws = AsyncMock()

    return client

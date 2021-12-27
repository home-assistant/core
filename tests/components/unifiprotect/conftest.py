"""Fixtures and test data for UniFi Protect methods."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from ipaddress import IPv4Address
import json
from pathlib import Path
from typing import Any, Callable
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pyunifiprotect.data import Camera, Version
from pyunifiprotect.data.websocket import WSSubscriptionMessage

from homeassistant.components.unifiprotect.const import DOMAIN, MIN_REQUIRED_PROTECT_V
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

MAC_ADDR = "aa:bb:cc:dd:ee:ff"


@dataclass
class MockPortData:
    """Mock Port information."""

    rtsp: int = 7441
    rtsps: int = 7447


@dataclass
class MockNvrData:
    """Mock for NVR."""

    version: Version
    mac: str
    name: str
    id: str
    ports: MockPortData = MockPortData()


@dataclass
class MockBootstrap:
    """Mock for Bootstrap."""

    nvr: MockNvrData
    cameras: dict[str, Any]
    lights: dict[str, Any]
    sensors: dict[str, Any]
    viewers: dict[str, Any]


@dataclass
class MockEntityFixture:
    """Mock for NVR."""

    entry: MockConfigEntry
    api: Mock


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

    client.base_url = "https://127.0.0.1"
    client.connection_host = IPv4Address("127.0.0.1")
    client.get_nvr = AsyncMock(return_value=MOCK_NVR_DATA)
    client.update = AsyncMock(return_value=MOCK_BOOTSTRAP)
    client.async_disconnect_ws = AsyncMock()

    def subscribe(ws_callback: Callable[[WSSubscriptionMessage], None]) -> Any:
        client.ws_subscription = ws_callback

        return Mock()

    client.subscribe_websocket = subscribe
    return client


@pytest.fixture
def mock_entry(hass: HomeAssistant, mock_client):
    """Mock ProtectApiClient for testing."""

    with patch("homeassistant.components.unifiprotect.ProtectApiClient") as mock_api:
        mock_config = MockConfigEntry(
            domain=DOMAIN,
            data={
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "id": "UnifiProtect",
                "port": 443,
                "verify_ssl": False,
            },
            version=2,
        )
        mock_config.add_to_hass(hass)

        mock_api.return_value = mock_client

        yield MockEntityFixture(mock_config, mock_client)


@pytest.fixture
def mock_camera():
    """Mock UniFi Protect Camera device."""

    path = Path(__file__).parent / "sample_data" / "sample_camera.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    yield Camera.from_unifi_dict(**data)


@pytest.fixture
async def simple_camera(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_camera: Camera
):
    """Fixture for a single camera, no extra setup."""

    camera = mock_camera.copy(deep=True)
    camera._api = mock_entry.api
    camera.channels[0]._api = mock_entry.api
    camera.channels[1]._api = mock_entry.api
    camera.channels[2]._api = mock_entry.api
    camera.name = "Test Camera"
    camera.channels[0].is_rtsp_enabled = True
    camera.channels[0].name = "High"
    camera.channels[1].is_rtsp_enabled = False
    camera.channels[2].is_rtsp_enabled = False

    mock_entry.api.bootstrap.cameras = {
        camera.id: camera,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    assert len(hass.states.async_all()) == 1
    assert len(entity_registry.entities) == 2

    yield (camera, "camera.test_camera_high")


async def time_changed(hass: HomeAssistant, seconds: int) -> None:
    """Trigger time changed."""
    next_update = dt_util.utcnow() + timedelta(seconds)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()


async def enable_entity(
    hass: HomeAssistant, entry_id: str, entity_id: str
) -> er.RegistryEntry:
    """Enable a disabled entity."""
    entity_registry = er.async_get(hass)

    updated_entity = entity_registry.async_update_entity(entity_id, disabled_by=None)
    assert not updated_entity.disabled
    await hass.config_entries.async_reload(entry_id)
    await hass.async_block_till_done()

    return updated_entity

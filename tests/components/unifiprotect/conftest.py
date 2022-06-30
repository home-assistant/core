"""Fixtures and test data for UniFi Protect methods."""
# pylint: disable=protected-access
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from ipaddress import IPv4Address
import json
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pyunifiprotect.data import (
    NVR,
    Camera,
    Doorlock,
    Light,
    Liveview,
    Sensor,
    Viewer,
    WSSubscriptionMessage,
)
from pyunifiprotect.data.base import ProtectAdoptableDeviceModel

from homeassistant.components.unifiprotect.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityDescription
import homeassistant.util.dt as dt_util

from . import _patch_discovery

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture

MAC_ADDR = "aa:bb:cc:dd:ee:ff"


@dataclass
class MockBootstrap:
    """Mock for Bootstrap."""

    nvr: NVR
    cameras: dict[str, Any]
    lights: dict[str, Any]
    sensors: dict[str, Any]
    viewers: dict[str, Any]
    liveviews: dict[str, Any]
    events: dict[str, Any]
    doorlocks: dict[str, Any]

    def reset_objects(self) -> None:
        """Reset all devices on bootstrap for tests."""
        self.cameras = {}
        self.lights = {}
        self.sensors = {}
        self.viewers = {}
        self.liveviews = {}
        self.events = {}
        self.doorlocks = {}

    def process_ws_packet(self, msg: WSSubscriptionMessage) -> None:
        """Fake process method for tests."""
        pass


@dataclass
class MockEntityFixture:
    """Mock for NVR."""

    entry: MockConfigEntry
    api: Mock


@pytest.fixture(name="mock_nvr")
def mock_nvr_fixture():
    """Mock UniFi Protect Camera device."""

    data = json.loads(load_fixture("sample_nvr.json", integration=DOMAIN))
    nvr = NVR.from_unifi_dict(**data)

    # disable pydantic validation so mocking can happen
    NVR.__config__.validate_assignment = False

    yield nvr

    NVR.__config__.validate_assignment = True


@pytest.fixture(name="mock_ufp_config_entry")
def mock_ufp_config_entry():
    """Mock the unifiprotect config entry."""

    return MockConfigEntry(
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


@pytest.fixture(name="mock_old_nvr")
def mock_old_nvr_fixture():
    """Mock UniFi Protect Camera device."""

    data = json.loads(load_fixture("sample_nvr.json", integration=DOMAIN))
    data["version"] = "1.19.0"
    return NVR.from_unifi_dict(**data)


@pytest.fixture(name="mock_bootstrap")
def mock_bootstrap_fixture(mock_nvr: NVR):
    """Mock Bootstrap fixture."""
    return MockBootstrap(
        nvr=mock_nvr,
        cameras={},
        lights={},
        sensors={},
        viewers={},
        liveviews={},
        events={},
        doorlocks={},
    )


@pytest.fixture
def mock_client(mock_bootstrap: MockBootstrap):
    """Mock ProtectApiClient for testing."""
    client = Mock()
    client.bootstrap = mock_bootstrap

    nvr = mock_bootstrap.nvr
    nvr._api = client

    client.base_url = "https://127.0.0.1"
    client.connection_host = IPv4Address("127.0.0.1")
    client.get_nvr = AsyncMock(return_value=nvr)
    client.update = AsyncMock(return_value=mock_bootstrap)
    client.async_disconnect_ws = AsyncMock()

    def subscribe(ws_callback: Callable[[WSSubscriptionMessage], None]) -> Any:
        client.ws_subscription = ws_callback

        return Mock()

    client.subscribe_websocket = subscribe
    return client


@pytest.fixture
def mock_entry(
    hass: HomeAssistant,
    mock_ufp_config_entry: MockConfigEntry,
    mock_client,  # pylint: disable=redefined-outer-name
):
    """Mock ProtectApiClient for testing."""

    with _patch_discovery(no_device=True), patch(
        "homeassistant.components.unifiprotect.ProtectApiClient"
    ) as mock_api:
        mock_ufp_config_entry.add_to_hass(hass)

        mock_api.return_value = mock_client

        yield MockEntityFixture(mock_ufp_config_entry, mock_client)


@pytest.fixture
def mock_liveview():
    """Mock UniFi Protect Liveview."""

    data = json.loads(load_fixture("sample_liveview.json", integration=DOMAIN))
    return Liveview.from_unifi_dict(**data)


@pytest.fixture
def mock_camera():
    """Mock UniFi Protect Camera device."""

    data = json.loads(load_fixture("sample_camera.json", integration=DOMAIN))
    return Camera.from_unifi_dict(**data)


@pytest.fixture
def mock_light():
    """Mock UniFi Protect Light device."""

    data = json.loads(load_fixture("sample_light.json", integration=DOMAIN))
    return Light.from_unifi_dict(**data)


@pytest.fixture
def mock_viewer():
    """Mock UniFi Protect Viewport device."""

    data = json.loads(load_fixture("sample_viewport.json", integration=DOMAIN))
    return Viewer.from_unifi_dict(**data)


@pytest.fixture
def mock_sensor():
    """Mock UniFi Protect Sensor device."""

    data = json.loads(load_fixture("sample_sensor.json", integration=DOMAIN))
    return Sensor.from_unifi_dict(**data)


@pytest.fixture
def mock_doorlock():
    """Mock UniFi Protect Doorlock device."""

    data = json.loads(load_fixture("sample_doorlock.json", integration=DOMAIN))
    return Doorlock.from_unifi_dict(**data)


@pytest.fixture
def now():
    """Return datetime object that will be consistent throughout test."""
    return dt_util.utcnow()


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


def assert_entity_counts(
    hass: HomeAssistant, platform: Platform, total: int, enabled: int
) -> None:
    """Assert entity counts for a given platform."""

    entity_registry = er.async_get(hass)

    entities = [
        e for e in entity_registry.entities if split_entity_id(e)[0] == platform.value
    ]

    assert len(entities) == total
    assert len(hass.states.async_all(platform.value)) == enabled


def ids_from_device_description(
    platform: Platform,
    device: ProtectAdoptableDeviceModel,
    description: EntityDescription,
) -> tuple[str, str]:
    """Return expected unique_id and entity_id for a give platform/device/description combination."""

    entity_name = (
        device.name.lower().replace(":", "").replace(" ", "_").replace("-", "_")
    )
    description_entity_name = (
        description.name.lower().replace(":", "").replace(" ", "_").replace("-", "_")
    )

    unique_id = f"{device.id}_{description.key}"
    entity_id = f"{platform.value}.{entity_name}_{description_entity_name}"

    return unique_id, entity_id

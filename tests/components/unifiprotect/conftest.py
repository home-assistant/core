"""Fixtures and test data for UniFi Protect methods."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from functools import partial
from ipaddress import IPv4Address
import json
from pathlib import Path
from tempfile import gettempdir
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pyunifiprotect import ProtectApiClient
from pyunifiprotect.data import (
    NVR,
    Bootstrap,
    Camera,
    Chime,
    CloudAccount,
    Doorlock,
    Light,
    Liveview,
    Sensor,
    SmartDetectObjectType,
    VideoMode,
    Viewer,
    WSSubscriptionMessage,
)

from homeassistant.components.unifiprotect.const import DOMAIN
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from . import _patch_discovery
from .utils import MockUFPFixture

from tests.common import MockConfigEntry, load_fixture

MAC_ADDR = "aa:bb:cc:dd:ee:ff"


@pytest.fixture(name="nvr")
def mock_nvr():
    """Mock UniFi Protect Camera device."""

    data = json.loads(load_fixture("sample_nvr.json", integration=DOMAIN))
    nvr = NVR.from_unifi_dict(**data)

    # disable pydantic validation so mocking can happen
    NVR.__config__.validate_assignment = False

    yield nvr

    NVR.__config__.validate_assignment = True


@pytest.fixture(name="ufp_config_entry")
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


@pytest.fixture(name="old_nvr")
def old_nvr():
    """Mock UniFi Protect Camera device."""

    data = json.loads(load_fixture("sample_nvr.json", integration=DOMAIN))
    data["version"] = "1.19.0"
    return NVR.from_unifi_dict(**data)


@pytest.fixture(name="bootstrap")
def bootstrap_fixture(nvr: NVR):
    """Mock Bootstrap fixture."""
    data = json.loads(load_fixture("sample_bootstrap.json", integration=DOMAIN))
    data["nvr"] = nvr
    data["cameras"] = []
    data["lights"] = []
    data["sensors"] = []
    data["viewers"] = []
    data["liveviews"] = []
    data["events"] = []
    data["doorlocks"] = []
    data["chimes"] = []

    return Bootstrap.from_unifi_dict(**data)


@pytest.fixture(name="ufp_client")
def mock_ufp_client(bootstrap: Bootstrap):
    """Mock ProtectApiClient for testing."""
    client = Mock()
    client.bootstrap = bootstrap
    client._bootstrap = bootstrap
    client.api_path = "/api"
    client.cache_dir = Path(gettempdir()) / "ufp_cache"
    # functionality from API client tests actually need
    client._stream_response = partial(ProtectApiClient._stream_response, client)
    client.get_camera_video = partial(ProtectApiClient.get_camera_video, client)

    nvr = client.bootstrap.nvr
    nvr._api = client
    client.bootstrap._api = client

    client.base_url = "https://127.0.0.1"
    client.connection_host = IPv4Address("127.0.0.1")
    client.get_nvr = AsyncMock(return_value=nvr)
    client.get_bootstrap = AsyncMock(return_value=bootstrap)
    client.update = AsyncMock(return_value=bootstrap)
    client.async_disconnect_ws = AsyncMock()
    return client


@pytest.fixture(name="ufp")
def mock_entry(
    hass: HomeAssistant, ufp_config_entry: MockConfigEntry, ufp_client: ProtectApiClient
):
    """Mock ProtectApiClient for testing."""

    with (
        _patch_discovery(no_device=True),
        patch(
            "homeassistant.components.unifiprotect.utils.ProtectApiClient"
        ) as mock_api,
    ):
        ufp_config_entry.add_to_hass(hass)

        mock_api.return_value = ufp_client

        ufp = MockUFPFixture(ufp_config_entry, ufp_client)

        def subscribe(ws_callback: Callable[[WSSubscriptionMessage], None]) -> Any:
            ufp.ws_subscription = ws_callback
            return Mock()

        ufp_client.subscribe_websocket = subscribe
        yield ufp


@pytest.fixture
def liveview():
    """Mock UniFi Protect Liveview."""

    data = json.loads(load_fixture("sample_liveview.json", integration=DOMAIN))
    return Liveview.from_unifi_dict(**data)


@pytest.fixture(name="camera")
def camera_fixture(fixed_now: datetime):
    """Mock UniFi Protect Camera device."""

    # disable pydantic validation so mocking can happen
    Camera.__config__.validate_assignment = False

    data = json.loads(load_fixture("sample_camera.json", integration=DOMAIN))
    camera = Camera.from_unifi_dict(**data)
    camera.last_motion = fixed_now - timedelta(hours=1)

    yield camera

    Camera.__config__.validate_assignment = True


@pytest.fixture(name="camera_all")
def camera_all_fixture(camera: Camera):
    """Mock UniFi Protect Camera device."""

    all_camera = camera.copy()
    all_camera.channels = [all_camera.channels[0].copy()]

    medium_channel = all_camera.channels[0].copy()
    medium_channel.name = "Medium"
    medium_channel.id = 1
    medium_channel.rtsp_alias = "test_medium_alias"
    all_camera.channels.append(medium_channel)

    low_channel = all_camera.channels[0].copy()
    low_channel.name = "Low"
    low_channel.id = 2
    low_channel.rtsp_alias = "test_medium_alias"
    all_camera.channels.append(low_channel)

    return all_camera


@pytest.fixture(name="doorbell")
def doorbell_fixture(camera: Camera, fixed_now: datetime):
    """Mock UniFi Protect Camera device (with chime)."""

    doorbell = camera.copy()
    doorbell.channels = [c.copy() for c in doorbell.channels]

    package_channel = doorbell.channels[0].copy()
    package_channel.name = "Package Camera"
    package_channel.id = 3
    package_channel.fps = 2
    package_channel.rtsp_alias = "test_package_alias"

    doorbell.channels.append(package_channel)
    doorbell.feature_flags.video_modes = [VideoMode.DEFAULT, VideoMode.HIGH_FPS]
    doorbell.feature_flags.smart_detect_types = [
        SmartDetectObjectType.PERSON,
        SmartDetectObjectType.VEHICLE,
    ]
    doorbell.has_speaker = True
    doorbell.feature_flags.has_hdr = True
    doorbell.feature_flags.has_lcd_screen = True
    doorbell.feature_flags.has_speaker = True
    doorbell.feature_flags.has_privacy_mask = True
    doorbell.feature_flags.is_doorbell = True
    doorbell.feature_flags.has_chime = True
    doorbell.feature_flags.has_smart_detect = True
    doorbell.feature_flags.has_package_camera = True
    doorbell.feature_flags.has_led_status = True
    doorbell.last_ring = fixed_now - timedelta(hours=1)
    return doorbell


@pytest.fixture
def unadopted_camera(camera: Camera):
    """Mock UniFi Protect Camera device (unadopted)."""

    no_camera = camera.copy()
    no_camera.channels = [c.copy() for c in no_camera.channels]
    no_camera.name = "Unadopted Camera"
    no_camera.is_adopted = False
    return no_camera


@pytest.fixture(name="light")
def light_fixture():
    """Mock UniFi Protect Light device."""

    # disable pydantic validation so mocking can happen
    Light.__config__.validate_assignment = False

    data = json.loads(load_fixture("sample_light.json", integration=DOMAIN))
    yield Light.from_unifi_dict(**data)

    Light.__config__.validate_assignment = True


@pytest.fixture
def unadopted_light(light: Light):
    """Mock UniFi Protect Light device (unadopted)."""

    no_light = light.copy()
    no_light.name = "Unadopted Light"
    no_light.is_adopted = False
    return no_light


@pytest.fixture
def viewer():
    """Mock UniFi Protect Viewport device."""

    # disable pydantic validation so mocking can happen
    Viewer.__config__.validate_assignment = False

    data = json.loads(load_fixture("sample_viewport.json", integration=DOMAIN))
    yield Viewer.from_unifi_dict(**data)

    Viewer.__config__.validate_assignment = True


@pytest.fixture(name="sensor")
def sensor_fixture(fixed_now: datetime):
    """Mock UniFi Protect Sensor device."""

    # disable pydantic validation so mocking can happen
    Sensor.__config__.validate_assignment = False

    data = json.loads(load_fixture("sample_sensor.json", integration=DOMAIN))
    sensor: Sensor = Sensor.from_unifi_dict(**data)
    sensor.motion_detected_at = fixed_now - timedelta(hours=1)
    sensor.open_status_changed_at = fixed_now - timedelta(hours=1)
    sensor.alarm_triggered_at = fixed_now - timedelta(hours=1)
    yield sensor

    Sensor.__config__.validate_assignment = True


@pytest.fixture(name="sensor_all")
def csensor_all_fixture(sensor: Sensor):
    """Mock UniFi Protect Sensor device."""

    all_sensor = sensor.copy()
    all_sensor.light_settings.is_enabled = True
    all_sensor.humidity_settings.is_enabled = True
    all_sensor.temperature_settings.is_enabled = True
    all_sensor.alarm_settings.is_enabled = True
    all_sensor.led_settings.is_enabled = True
    all_sensor.motion_settings.is_enabled = True

    return all_sensor


@pytest.fixture(name="doorlock")
def doorlock_fixture():
    """Mock UniFi Protect Doorlock device."""

    # disable pydantic validation so mocking can happen
    Doorlock.__config__.validate_assignment = False

    data = json.loads(load_fixture("sample_doorlock.json", integration=DOMAIN))
    yield Doorlock.from_unifi_dict(**data)

    Doorlock.__config__.validate_assignment = True


@pytest.fixture
def unadopted_doorlock(doorlock: Doorlock):
    """Mock UniFi Protect Light device (unadopted)."""

    no_doorlock = doorlock.copy()
    no_doorlock.name = "Unadopted Lock"
    no_doorlock.is_adopted = False
    return no_doorlock


@pytest.fixture
def chime():
    """Mock UniFi Protect Chime device."""

    # disable pydantic validation so mocking can happen
    Chime.__config__.validate_assignment = False

    data = json.loads(load_fixture("sample_chime.json", integration=DOMAIN))
    yield Chime.from_unifi_dict(**data)

    Chime.__config__.validate_assignment = True


@pytest.fixture(name="fixed_now")
def fixed_now_fixture():
    """Return datetime object that will be consistent throughout test."""
    return dt_util.utcnow()


@pytest.fixture(name="cloud_account")
def cloud_account() -> CloudAccount:
    """Return UI Cloud Account."""

    return CloudAccount(
        id="42",
        first_name="Test",
        last_name="User",
        email="test@example.com",
        user_id="42",
        name="Test User",
        location=None,
        profile_img=None,
    )

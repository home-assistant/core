"""Fixtures and test data for UniFi Protect methods."""

from __future__ import annotations

from collections.abc import Callable, Generator
from datetime import datetime, timedelta
from functools import partial
from ipaddress import IPv4Address
from pathlib import Path
from tempfile import gettempdir
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from uiprotect import ProtectApiClient
from uiprotect.data import (
    NVR,
    AiPort,
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
from uiprotect.websocket import WebsocketState

from homeassistant.components.unifiprotect.const import DOMAIN
from homeassistant.components.unifiprotect.utils import _async_unifi_mac_from_hass
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import _patch_discovery
from .utils import MockUFPFixture

from tests.common import MockConfigEntry, load_json_object_fixture

MAC_ADDR = "aa:bb:cc:dd:ee:ff"

# Common test data constants
DEFAULT_HOST = "1.1.1.1"
DEFAULT_PORT = 443
DEFAULT_VERIFY_SSL = False
DEFAULT_USERNAME = "test-username"
DEFAULT_PASSWORD = "test-password"
DEFAULT_API_KEY = "test-api-key"


@pytest.fixture(name="nvr")
def mock_nvr():
    """Mock UniFi Protect Camera device."""

    data = load_json_object_fixture("sample_nvr.json", DOMAIN)
    nvr = NVR.from_unifi_dict(**data)

    # disable pydantic validation so mocking can happen
    NVR.model_config["validate_assignment"] = False

    yield nvr

    NVR.model_config["validate_assignment"] = True


@pytest.fixture(name="ufp_config_entry")
def mock_ufp_config_entry():
    """Mock the unifiprotect config entry."""

    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: DEFAULT_HOST,
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: DEFAULT_PASSWORD,
            CONF_API_KEY: DEFAULT_API_KEY,
            "id": "UnifiProtect",
            CONF_PORT: DEFAULT_PORT,
            CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
        },
        version=2,
        unique_id="A1E00C826924",
    )


@pytest.fixture(name="old_nvr")
def old_nvr():
    """Mock UniFi Protect Camera device."""

    data = load_json_object_fixture("sample_nvr.json", DOMAIN)
    data["version"] = "1.19.0"
    return NVR.from_unifi_dict(**data)


@pytest.fixture(name="bootstrap")
def bootstrap_fixture(nvr: NVR):
    """Mock Bootstrap fixture."""
    data = load_json_object_fixture("sample_bootstrap.json", DOMAIN)
    data["nvr"] = nvr
    data["cameras"] = []
    data["lights"] = []
    data["sensors"] = []
    data["viewers"] = []
    data["liveviews"] = []
    data["events"] = []
    data["doorlocks"] = []
    data["chimes"] = []
    data["aiports"] = []

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

    async def get_nvr(*args: Any, **kwargs: Any) -> NVR:
        return client.bootstrap.nvr

    client.get_nvr = get_nvr
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

        def subscribe_websocket_state(
            ws_state_subscription: Callable[[WebsocketState], None],
        ) -> Any:
            ufp.ws_state_subscription = ws_state_subscription
            return Mock()

        ufp_client.subscribe_websocket = subscribe
        ufp_client.subscribe_websocket_state = subscribe_websocket_state
        yield ufp


@pytest.fixture
def liveview():
    """Mock UniFi Protect Liveview."""

    data = load_json_object_fixture("sample_liveview.json", DOMAIN)
    return Liveview.from_unifi_dict(**data)


@pytest.fixture(name="camera")
def camera_fixture(fixed_now: datetime):
    """Mock UniFi Protect Camera device."""

    # disable pydantic validation so mocking can happen
    Camera.model_config["validate_assignment"] = False

    data = load_json_object_fixture("sample_camera.json", DOMAIN)
    camera = Camera.from_unifi_dict(**data)
    camera.last_motion = fixed_now - timedelta(hours=1)

    yield camera

    Camera.model_config["validate_assignment"] = True


@pytest.fixture(name="camera_all")
def camera_all_fixture(camera: Camera):
    """Mock UniFi Protect Camera device."""

    all_camera = camera.model_copy()
    all_camera.channels = [all_camera.channels[0].model_copy()]

    medium_channel = all_camera.channels[0].model_copy()
    medium_channel.name = "Medium"
    medium_channel.id = 1
    medium_channel.rtsp_alias = "test_medium_alias"
    all_camera.channels.append(medium_channel)

    low_channel = all_camera.channels[0].model_copy()
    low_channel.name = "Low"
    low_channel.id = 2
    low_channel.rtsp_alias = "test_medium_alias"
    all_camera.channels.append(low_channel)

    return all_camera


@pytest.fixture(name="camera_all_features")
def camera_all_features_fixture(fixed_now: datetime):
    """Mock UniFi Protect Camera device with all features enabled."""

    # disable pydantic validation so mocking can happen
    Camera.model_config["validate_assignment"] = False

    data = load_json_object_fixture("sample_camera_all_features.json", DOMAIN)
    camera = Camera.from_unifi_dict(**data)
    camera.last_motion = fixed_now - timedelta(hours=1)

    yield camera

    Camera.model_config["validate_assignment"] = True


@pytest.fixture(name="doorbell")
def doorbell_fixture(camera: Camera, fixed_now: datetime):
    """Mock UniFi Protect Camera device (with chime)."""

    doorbell = camera.model_copy()
    doorbell.channels = [c.model_copy() for c in doorbell.channels]

    package_channel = doorbell.channels[0].model_copy()
    package_channel.name = "Package Camera"
    package_channel.id = 3
    package_channel.fps = 2
    package_channel.rtsp_alias = "test_package_alias"

    doorbell.channels.append(package_channel)
    doorbell.feature_flags.video_modes = [VideoMode.DEFAULT, VideoMode.HIGH_FPS]
    doorbell.feature_flags.smart_detect_types = [
        SmartDetectObjectType.PERSON,
        SmartDetectObjectType.VEHICLE,
        SmartDetectObjectType.ANIMAL,
        SmartDetectObjectType.PACKAGE,
    ]
    doorbell.has_speaker = True
    doorbell.feature_flags.has_hdr = True
    doorbell.feature_flags.has_lcd_screen = True
    doorbell.feature_flags.has_speaker = True
    doorbell.feature_flags.has_privacy_mask = True
    doorbell.feature_flags.is_doorbell = True
    doorbell.feature_flags.has_fingerprint_sensor = True
    doorbell.feature_flags.support_nfc = True
    doorbell.feature_flags.has_chime = True
    doorbell.feature_flags.has_smart_detect = True
    doorbell.feature_flags.has_package_camera = True
    doorbell.feature_flags.has_led_status = True
    doorbell.last_ring = fixed_now - timedelta(hours=1)
    return doorbell


@pytest.fixture
def unadopted_camera(camera: Camera):
    """Mock UniFi Protect Camera device (unadopted)."""

    no_camera = camera.model_copy()
    no_camera.channels = [c.model_copy() for c in no_camera.channels]
    no_camera.name = "Unadopted Camera"
    no_camera.is_adopted = False
    return no_camera


@pytest.fixture(name="light")
def light_fixture():
    """Mock UniFi Protect Light device."""

    # disable pydantic validation so mocking can happen
    Light.model_config["validate_assignment"] = False

    data = load_json_object_fixture("sample_light.json", DOMAIN)
    yield Light.from_unifi_dict(**data)

    Light.model_config["validate_assignment"] = True


@pytest.fixture
def unadopted_light(light: Light):
    """Mock UniFi Protect Light device (unadopted)."""

    no_light = light.model_copy()
    no_light.name = "Unadopted Light"
    no_light.is_adopted = False
    return no_light


@pytest.fixture
def viewer():
    """Mock UniFi Protect Viewport device."""

    # disable pydantic validation so mocking can happen
    Viewer.model_config["validate_assignment"] = False

    data = load_json_object_fixture("sample_viewport.json", DOMAIN)
    yield Viewer.from_unifi_dict(**data)

    Viewer.model_config["validate_assignment"] = True


@pytest.fixture(name="sensor")
def sensor_fixture(fixed_now: datetime):
    """Mock UniFi Protect Sensor device."""

    # disable pydantic validation so mocking can happen
    Sensor.model_config["validate_assignment"] = False

    data = load_json_object_fixture("sample_sensor.json", DOMAIN)
    sensor: Sensor = Sensor.from_unifi_dict(**data)
    sensor.motion_detected_at = fixed_now - timedelta(hours=1)
    sensor.open_status_changed_at = fixed_now - timedelta(hours=1)
    sensor.alarm_triggered_at = fixed_now - timedelta(hours=1)
    yield sensor

    Sensor.model_config["validate_assignment"] = True


@pytest.fixture(name="sensor_all")
def sensor_all_fixture(sensor: Sensor):
    """Mock UniFi Protect Sensor device."""

    all_sensor = sensor.model_copy()
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
    Doorlock.model_config["validate_assignment"] = False

    data = load_json_object_fixture("sample_doorlock.json", DOMAIN)
    yield Doorlock.from_unifi_dict(**data)

    Doorlock.model_config["validate_assignment"] = True


@pytest.fixture
def unadopted_doorlock(doorlock: Doorlock):
    """Mock UniFi Protect Light device (unadopted)."""

    no_doorlock = doorlock.model_copy()
    no_doorlock.name = "Unadopted Lock"
    no_doorlock.is_adopted = False
    return no_doorlock


@pytest.fixture
def chime():
    """Mock UniFi Protect Chime device."""

    # disable pydantic validation so mocking can happen
    Chime.model_config["validate_assignment"] = False

    data = load_json_object_fixture("sample_chime.json", DOMAIN)
    yield Chime.from_unifi_dict(**data)

    Chime.model_config["validate_assignment"] = True


@pytest.fixture(name="aiport")
def aiport_fixture():
    """Mock UniFi Protect AI Port device."""

    # disable pydantic validation so mocking can happen
    AiPort.model_config["validate_assignment"] = False

    data = load_json_object_fixture("sample_aiport.json", DOMAIN)
    yield AiPort.from_unifi_dict(**data)

    AiPort.model_config["validate_assignment"] = True


@pytest.fixture(name="fixed_now")
def fixed_now_fixture():
    """Return datetime object that will be consistent throughout test."""
    return dt_util.utcnow()


@pytest.fixture(name="ufp_reauth_entry")
def mock_ufp_reauth_entry():
    """Mock the unifiprotect config entry for reauth and reconfigure tests."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: DEFAULT_HOST,
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: DEFAULT_PASSWORD,
            CONF_API_KEY: DEFAULT_API_KEY,
            "id": "UnifiProtect",
            CONF_PORT: DEFAULT_PORT,
            CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
        },
        unique_id=_async_unifi_mac_from_hass(MAC_ADDR),
    )


@pytest.fixture(name="ufp_reauth_entry_alt")
def mock_ufp_reauth_entry_alt():
    """Mock the unifiprotect config entry with alternate port/SSL for reauth/reconfigure tests."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: DEFAULT_HOST,
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: DEFAULT_PASSWORD,
            CONF_API_KEY: DEFAULT_API_KEY,
            "id": "UnifiProtect",
            CONF_PORT: 8443,
            CONF_VERIFY_SSL: True,
        },
        unique_id=_async_unifi_mac_from_hass(MAC_ADDR),
    )


@pytest.fixture(name="mock_setup")
def mock_setup_fixture() -> Generator[AsyncMock]:
    """Mock async_setup and async_setup_entry to prevent reload issues in tests."""
    with (
        patch(
            "homeassistant.components.unifiprotect.async_setup",
            return_value=True,
        ),
        patch(
            "homeassistant.components.unifiprotect.async_setup_entry",
            return_value=True,
        ) as mock,
    ):
        yield mock


@pytest.fixture(name="mock_api_bootstrap")
def mock_api_bootstrap_fixture(bootstrap: Bootstrap):
    """Mock the ProtectApiClient.get_bootstrap method."""
    with patch(
        "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_bootstrap",
        return_value=bootstrap,
    ) as mock:
        yield mock


@pytest.fixture(name="mock_api_meta_info")
def mock_api_meta_info_fixture():
    """Mock the ProtectApiClient.get_meta_info method."""
    with patch(
        "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_meta_info",
        return_value=None,
    ) as mock:
        yield mock


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

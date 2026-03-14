"""Common fixtures for the Sunricher DALI tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from PySrDaliGateway.helper import gen_device_unique_id, gen_group_unique_id
import pytest

from homeassistant.components.sunricher_dali.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

GATEWAY_SERIAL = "6A242121110E"
GATEWAY_HOST = "192.168.1.100"
GATEWAY_PORT = 1883

DEVICE_DATA: list[dict[str, Any]] = [
    {
        "dev_id": "01010000026A242121110E",
        "dev_type": "0101",
        "name": "Dimmer 0000-02",
        "model": "DALI DT6 Dimmable Driver",
        "color_mode": "brightness",
        "address": 2,
        "channel": 0,
    },
    {
        "dev_id": "01020000036A242121110E",
        "dev_type": "0102",
        "name": "CCT 0000-03",
        "model": "DALI DT8 Tc Dimmable Driver",
        "color_mode": "color_temp",
        "address": 3,
        "channel": 0,
    },
    {
        "dev_id": "01030000046A242121110E",
        "dev_type": "0103",
        "name": "HS Color Light",
        "model": "DALI HS Color Driver",
        "color_mode": "hs",
        "address": 4,
        "channel": 0,
    },
    {
        "dev_id": "01040000056A242121110E",
        "dev_type": "0104",
        "name": "RGBW Light",
        "model": "DALI RGBW Driver",
        "color_mode": "rgbw",
        "address": 5,
        "channel": 0,
    },
]

ILLUMINANCE_SENSOR_DATA: dict[str, Any] = {
    "dev_id": "02020000206A242121110E",
    "dev_type": "0202",
    "name": "Illuminance Sensor 0000-20",
    "model": "DALI Illuminance Sensor",
    "color_mode": None,
    "address": 20,
    "channel": 0,
}

# Light device data for energy sensor testing (reuse first device from DEVICE_DATA)
LIGHT_DEVICE_DATA: dict[str, Any] = DEVICE_DATA[0]

MOTION_SENSOR_DATA: dict[str, Any] = {
    "dev_id": "02010000106A242121110E",
    "dev_type": "0201",
    "name": "Motion Sensor 0000-10",
    "model": "DALI Motion Sensor",
    "color_mode": None,
    "address": 10,
    "channel": 0,
}


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
    mock_devices: list[MagicMock],
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.sunricher_dali._PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL_NUMBER: GATEWAY_SERIAL,
            CONF_HOST: GATEWAY_HOST,
            CONF_PORT: GATEWAY_PORT,
            CONF_NAME: "Test Gateway",
            CONF_USERNAME: "gateway_user",
            CONF_PASSWORD: "gateway_pass",
        },
        unique_id=GATEWAY_SERIAL,
        title="Test Gateway",
    )


def _create_mock_device(device_data: dict[str, Any]) -> MagicMock:
    """Create a mock device from device data dict."""
    device = MagicMock()
    device.dev_id = device_data["dev_id"]
    device.unique_id = device_data["dev_id"]
    device.status = "online"
    device.dev_type = device_data["dev_type"]
    device.name = device_data["name"]
    device.model = device_data["model"]
    device.gw_sn = GATEWAY_SERIAL
    device.color_mode = device_data["color_mode"]
    device.turn_on = MagicMock()
    device.turn_off = MagicMock()
    device.read_status = MagicMock()
    device.register_listener = MagicMock(return_value=lambda: None)
    return device


@pytest.fixture
def mock_devices() -> list[MagicMock]:
    """Return mocked Device objects."""
    devices = [_create_mock_device(data) for data in DEVICE_DATA]
    devices.append(_create_mock_device(DEVICE_DATA[0]))
    return devices


@pytest.fixture
def mock_illuminance_device() -> MagicMock:
    """Return a mocked illuminance sensor device."""
    return _create_mock_device(ILLUMINANCE_SENSOR_DATA)


@pytest.fixture
def mock_light_device() -> MagicMock:
    """Return a mocked light device for energy sensor testing."""
    return _create_mock_device(LIGHT_DEVICE_DATA)


@pytest.fixture
def mock_motion_sensor_device() -> MagicMock:
    """Return a mocked motion sensor device."""
    return _create_mock_device(MOTION_SENSOR_DATA)


def _create_scene_device_property(
    dev_type: str, brightness: int = 128, **kwargs: Any
) -> dict[str, Any]:
    """Create scene device property dict with defaults."""
    return {
        "is_on": True,
        "brightness": brightness,
        "color_temp_kelvin": kwargs.get("color_temp_kelvin"),
        "hs_color": kwargs.get("hs_color"),
        "rgbw_color": kwargs.get("rgbw_color"),
        "white_level": kwargs.get("white_level"),
    }


@pytest.fixture
def mock_discovery(mock_gateway: MagicMock) -> Generator[MagicMock]:
    """Mock DaliGatewayDiscovery."""
    with patch(
        "homeassistant.components.sunricher_dali.config_flow.DaliGatewayDiscovery"
    ) as mock_discovery_class:
        mock_discovery = mock_discovery_class.return_value
        mock_discovery.discover_gateways = AsyncMock(return_value=[mock_gateway])
        yield mock_discovery


def _create_mock_scene(
    scene_id: int,
    name: str,
    unique_id: str,
    channel: int,
    area_id: str,
    devices: list[dict[str, Any]],
    gw_sn: str = GATEWAY_SERIAL,
) -> MagicMock:
    """Create a mock scene with standard attributes."""
    devices_with_ids: list[dict[str, Any]] = []
    for device in devices:
        device_with_id = dict(device)
        device_with_id["unique_id"] = (
            gen_group_unique_id(device["address"], device["channel"], gw_sn)
            if device["dev_type"] == "0401"
            else gen_device_unique_id(
                device["dev_type"],
                device["channel"],
                device["address"],
                gw_sn,
            )
        )
        devices_with_ids.append(device_with_id)

    scene = MagicMock()
    scene.scene_id = scene_id
    scene.name = name
    scene.unique_id = unique_id
    scene.gw_sn = gw_sn
    scene.channel = channel
    scene.activate = MagicMock()
    scene.devices = devices_with_ids

    scene_details: dict[str, Any] = {
        "unique_id": unique_id,
        "id": scene_id,
        "name": name,
        "channel": channel,
        "area_id": area_id,
        "devices": devices_with_ids,
    }
    scene.read_scene = AsyncMock(return_value=scene_details)
    scene.register_listener = MagicMock(return_value=lambda: None)
    return scene


@pytest.fixture
def mock_scenes() -> list[MagicMock]:
    """Return mocked Scene objects."""
    return [
        _create_mock_scene(
            scene_id=1,
            name="Living Room Evening",
            unique_id=f"scene_0001_0000_{GATEWAY_SERIAL}",
            channel=0,
            area_id="1",
            devices=[
                {
                    "dev_type": DEVICE_DATA[0]["dev_type"],
                    "channel": DEVICE_DATA[0]["channel"],
                    "address": DEVICE_DATA[0]["address"],
                    "gw_sn_obj": "",
                    "property": _create_scene_device_property("0101", brightness=128),
                },
                {
                    "dev_type": DEVICE_DATA[1]["dev_type"],
                    "channel": DEVICE_DATA[1]["channel"],
                    "address": DEVICE_DATA[1]["address"],
                    "gw_sn_obj": "",
                    "property": _create_scene_device_property(
                        "0102", brightness=200, color_temp_kelvin=3000
                    ),
                },
            ],
        ),
        _create_mock_scene(
            scene_id=2,
            name="Kitchen Bright",
            unique_id=f"scene_0002_0000_{GATEWAY_SERIAL}",
            channel=0,
            area_id="2",
            devices=[
                {
                    "dev_type": "0401",
                    "channel": 0,
                    "address": 1,
                    "gw_sn_obj": "",
                    "property": _create_scene_device_property("0401", brightness=255),
                },
            ],
        ),
    ]


@pytest.fixture
def mock_gateway(
    mock_devices: list[MagicMock], mock_scenes: list[MagicMock]
) -> Generator[MagicMock]:
    """Return a mocked DaliGateway."""
    with (
        patch(
            "homeassistant.components.sunricher_dali.DaliGateway", autospec=True
        ) as mock_gateway_class,
        patch(
            "homeassistant.components.sunricher_dali.config_flow.DaliGateway",
            new=mock_gateway_class,
        ),
    ):
        mock_gateway = mock_gateway_class.return_value
        mock_gateway.gw_sn = GATEWAY_SERIAL
        mock_gateway.gw_ip = GATEWAY_HOST
        mock_gateway.port = GATEWAY_PORT
        mock_gateway.name = "Test Gateway"
        mock_gateway.username = "gateway_user"
        mock_gateway.passwd = "gateway_pass"
        mock_gateway.connect = AsyncMock()
        mock_gateway.disconnect = AsyncMock()
        mock_gateway.discover_devices = AsyncMock(return_value=mock_devices)
        mock_gateway.discover_scenes = AsyncMock(return_value=mock_scenes)
        yield mock_gateway


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sunricher_dali.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry

"""Test nest diagnostics."""
from unittest.mock import patch

from google_nest_sdm.exceptions import SubscriberException
import pytest

from homeassistant.components.nest.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator

NEST_DEVICE_ID = "enterprises/project-id/devices/device-id"

DEVICE_API_DATA = {
    "name": NEST_DEVICE_ID,
    "type": "sdm.devices.types.THERMOSTAT",
    "assignee": "enterprises/project-id/structures/structure-id/rooms/room-id",
    "traits": {
        "sdm.devices.traits.Info": {
            "customName": "My Sensor",
        },
        "sdm.devices.traits.Temperature": {
            "ambientTemperatureCelsius": 25.1,
        },
        "sdm.devices.traits.Humidity": {
            "ambientHumidityPercent": 35.0,
        },
    },
    "parentRelations": [
        {
            "parent": "enterprises/project-id/structures/structure-id/rooms/room-id",
            "displayName": "Lobby",
        }
    ],
}

DEVICE_DIAGNOSTIC_DATA = {
    "data": {
        "assignee": "**REDACTED**",
        "name": "**REDACTED**",
        "parentRelations": [{"displayName": "**REDACTED**", "parent": "**REDACTED**"}],
        "traits": {
            "sdm.devices.traits.Info": {"customName": "**REDACTED**"},
            "sdm.devices.traits.Humidity": {"ambientHumidityPercent": 35.0},
            "sdm.devices.traits.Temperature": {"ambientTemperatureCelsius": 25.1},
        },
        "type": "sdm.devices.types.THERMOSTAT",
    }
}


CAMERA_API_DATA = {
    "name": NEST_DEVICE_ID,
    "type": "sdm.devices.types.CAMERA",
    "traits": {
        "sdm.devices.traits.CameraLiveStream": {
            "videoCodecs": "H264",
            "supportedProtocols": ["RTSP"],
        },
    },
}

CAMERA_DIAGNOSTIC_DATA = {
    "data": {
        "name": "**REDACTED**",
        "traits": {
            "sdm.devices.traits.CameraLiveStream": {
                "videoCodecs": "H264",
                "supportedProtocols": ["RTSP"],
            },
        },
        "type": "sdm.devices.types.CAMERA",
    },
}


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return ["sensor", "camera"]


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    create_device,
    setup_platform,
    config_entry,
) -> None:
    """Test config entry diagnostics."""
    create_device.create(raw_data=DEVICE_API_DATA)
    await setup_platform()
    assert config_entry.state is ConfigEntryState.LOADED

    # Test that only non identifiable device information is returned
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "devices": [DEVICE_DIAGNOSTIC_DATA]
    }


async def test_device_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    create_device,
    setup_platform,
    config_entry,
) -> None:
    """Test config entry diagnostics."""
    create_device.create(raw_data=DEVICE_API_DATA)
    await setup_platform()
    assert config_entry.state is ConfigEntryState.LOADED

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, NEST_DEVICE_ID)})
    assert device is not None

    assert (
        await get_diagnostics_for_device(hass, hass_client, config_entry, device)
        == DEVICE_DIAGNOSTIC_DATA
    )


async def test_setup_susbcriber_failure(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry,
    setup_base_platform,
) -> None:
    """Test configuration error."""
    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber.start_async",
        side_effect=SubscriberException(),
    ):
        await setup_base_platform()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY

    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {}


async def test_camera_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    create_device,
    setup_platform,
    config_entry,
) -> None:
    """Test config entry diagnostics."""
    create_device.create(raw_data=CAMERA_API_DATA)
    await setup_platform()
    assert config_entry.state is ConfigEntryState.LOADED

    # Test that only non identifiable device information is returned
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "devices": [CAMERA_DIAGNOSTIC_DATA],
        "camera": {"camera.camera": {}},
    }

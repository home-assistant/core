"""Tests configuration for Govee Local API."""

from asyncio import AbstractEventLoop, Event
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from govee_local_api import GoveeDevice, GoveeLightCapabilities, GoveeLightFeatures
from govee_local_api.device_registry import DeviceRegistry
from govee_local_api.light_capabilities import COMMON_FEATURES, SCENE_CODES
import pytest

from homeassistant.components.govee_light_local.coordinator import GoveeController


def set_mocked_devices(mock_govee_api: AsyncMock, devices: list[GoveeDevice]) -> None:
    """Update a mocked device."""
    devices_dict = {device.fingerprint: device for device in devices}
    devices_list = list(devices_dict.values())
    mock_govee_api._registry._discovered_devices = devices_dict

    type(mock_govee_api).devices = PropertyMock(return_value=devices_list)

    mock_govee_api.get_device_by_ip.side_effect = lambda ip: next(
        (device for device in devices_list if device.ip == ip), None
    )

    mock_govee_api.get_device_by_sku.side_effect = lambda sku: next(
        (device for device in devices_list if device.sku == sku), None
    )

    mock_govee_api.get_device_by_fingerprint.side_effect = lambda fingerprint: next(
        (device for device in devices_list if device.fingerprint == fingerprint), None
    )


@pytest.fixture(name="mock_coordinator")
def fixture_mock_coordinator() -> Generator[AsyncMock]:
    """Set up Govee Local API coordinator fixture."""
    mock_coordinator = AsyncMock()
    mock_coordinator.devices = []
    mock_coordinator.discovery_queue = []
    return mock_coordinator


@pytest.fixture(name="mock_govee_api")
def fixture_mock_govee_api(event_loop: AbstractEventLoop) -> Generator[AsyncMock]:
    """Set up Govee Local API fixture."""

    mock_registry = MagicMock(spec=DeviceRegistry, wraps=DeviceRegistry)
    mock_registry._discovered_devices = {}

    controller = GoveeController(event_loop)
    controller._registry = mock_registry

    mock_api = AsyncMock(spec=GoveeController)
    mock_api._registry = mock_registry

    mock_api.start = AsyncMock()
    mock_api.cleanup = MagicMock(return_value=Event())
    mock_api.cleanup.return_value.set()
    mock_api.turn_on_off = AsyncMock()
    mock_api.set_brightness = AsyncMock()
    mock_api.set_color = AsyncMock()
    mock_api.set_scene = AsyncMock()
    mock_api._async_update_data = AsyncMock()
    mock_api.get_device_by_ip = MagicMock()
    mock_api.get_device_by_sku = MagicMock()
    mock_api.get_device_by_fingerprint = MagicMock()
    mock_api.set_discovery_enabled = MagicMock()

    type(mock_api).devices = PropertyMock(return_value=[])

    with (
        patch(
            "homeassistant.components.govee_light_local.coordinator.GoveeController",
            return_value=mock_api,
        ) as mock_controller,
        patch(
            "homeassistant.components.govee_light_local.config_flow.GoveeController",
            return_value=mock_api,
        ),
    ):
        yield mock_controller.return_value


@pytest.fixture(name="mock_setup_entry")
def fixture_mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.govee_light_local.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


DEFAULT_CAPABILITIES: GoveeLightCapabilities = GoveeLightCapabilities(
    features=COMMON_FEATURES, segments=[], scenes={}
)

SCENE_CAPABILITIES: GoveeLightCapabilities = GoveeLightCapabilities(
    features=COMMON_FEATURES | GoveeLightFeatures.SCENES,
    segments=[],
    scenes=SCENE_CODES,
)

"""Tests for the overkiz component."""

from collections import defaultdict
from copy import deepcopy
from functools import cache
import logging
from typing import Any

import humps
from pyoverkiz.enums import UIClass
from pyoverkiz.models import Device, Setup, State

from homeassistant.components.overkiz import HomeAssistantOverkizData
from homeassistant.components.overkiz.coordinator import OverkizDataUpdateCoordinator
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture

DEFAULT_SETUP_FIXTURE = "overkiz/setup/setup_tahoma_switch.json"
LOGGER = logging.getLogger(__name__)


def load_setup_fixture(fixture: str = DEFAULT_SETUP_FIXTURE) -> Setup:
    """Return setup from fixture."""
    setup_json = load_json_object_fixture(fixture)
    return Setup(**humps.decamelize(setup_json))


@cache
def get_fixture_setup(fixture: str = DEFAULT_SETUP_FIXTURE) -> Setup:
    """Return a cached setup fixture."""
    return load_setup_fixture(fixture)


def get_fixture_device(
    fixture: str = DEFAULT_SETUP_FIXTURE,
    *,
    index: int | None = None,
    device_url: str | None = None,
    ui_class: UIClass | None = None,
) -> Device:
    """Return a device from a setup fixture.

    Selectors are intended for future fixture-heavy tests where device index alone
    is not descriptive enough.
    """
    devices = get_fixture_setup(fixture).devices

    if index is not None:
        return devices[index]

    matches = devices
    if device_url is not None:
        matches = [device for device in matches if device.device_url == device_url]
    if ui_class is not None:
        matches = [device for device in matches if device.ui_class == ui_class]

    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one device for fixture={fixture!r}, "
            f"device_url={device_url!r}, ui_class={ui_class!r}; found {len(matches)}"
        )

    return matches[0]


def clone_device(
    device: Device,
    *,
    device_url: str,
    ui_class: UIClass,
    commands: list[str] | None = None,
    states: dict[str, Any] | None = None,
    widget: str | None = None,
    label: str = "Test Device",
) -> Device:
    """Clone a fixture device and override the fields relevant to a test."""
    device = deepcopy(device)
    device_states = defaultdict(
        lambda: None,
        {
            str(name): State(name=str(name), type=2, value=value)
            for name, value in (states or {}).items()
        },
    )

    device.attributes = defaultdict(lambda: None)
    device.available = True
    device.controllable_name = "Test Cover"
    if commands is not None:
        device.definition.commands = commands
    device.device_url = device_url
    device.label = label
    device.place_oid = None
    device.states = device_states
    device.ui_class = ui_class
    if widget is not None:
        device.widget = widget

    return device


class MockOverkizServer:
    """Minimal Overkiz server object for tests."""

    configuration_url = "https://example.test"
    manufacturer = "Somfy"


class MockOverkizClient:
    """Minimal Overkiz client object for tests."""

    def __init__(self) -> None:
        """Initialize the test client."""
        self.server = MockOverkizServer()


def create_coordinator(
    hass: HomeAssistant, config_entry: MockConfigEntry, *devices: Device
) -> OverkizDataUpdateCoordinator:
    """Create a real Overkiz coordinator for entity tests."""
    coordinator = OverkizDataUpdateCoordinator(
        hass,
        config_entry,
        LOGGER,
        client=MockOverkizClient(),
        devices=list(devices),
        places=None,
    )
    coordinator.data = coordinator.devices
    coordinator.last_update_success = True
    return coordinator


def set_runtime_data(
    config_entry: MockConfigEntry,
    coordinator: OverkizDataUpdateCoordinator,
    *,
    platforms: dict[Platform, list[Device]],
) -> MockConfigEntry:
    """Attach runtime data to a config entry for platform tests."""
    config_entry.runtime_data = HomeAssistantOverkizData(
        coordinator=coordinator,
        platforms=defaultdict(list, platforms),
        scenarios=[],
    )
    return config_entry

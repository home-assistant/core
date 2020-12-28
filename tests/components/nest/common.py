"""Common libraries for test setup."""

import time
from typing import Awaitable, Callable

from google_nest_sdm.device_manager import DeviceManager
from google_nest_sdm.event import EventMessage
from google_nest_sdm.google_nest_subscriber import GoogleNestSubscriber

from homeassistant.components.nest import DOMAIN
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.common import MockConfigEntry

CONFIG = {
    "nest": {
        "client_id": "some-client-id",
        "client_secret": "some-client-secret",
        # Required fields for using SDM API
        "project_id": "some-project-id",
        "subscriber_id": "projects/example/subscriptions/subscriber-id-9876",
    },
}

CONFIG_ENTRY_DATA = {
    "sdm": {},  # Indicates new SDM API, not legacy API
    "auth_implementation": "local",
    "token": {
        "expires_at": time.time() + 86400,
        "access_token": {
            "token": "some-token",
        },
    },
}


class FakeDeviceManager(DeviceManager):
    """Fake DeviceManager that can supply a list of devices and structures."""

    def __init__(self, devices: dict, structures: dict):
        """Initialize FakeDeviceManager."""
        super().__init__()
        self._devices = devices

    @property
    def structures(self) -> dict:
        """Override structures with fake result."""
        return self._structures

    @property
    def devices(self) -> dict:
        """Override devices with fake result."""
        return self._devices


class FakeSubscriber(GoogleNestSubscriber):
    """Fake subscriber that supplies a FakeDeviceManager."""

    def __init__(self, device_manager: FakeDeviceManager):
        """Initialize Fake Subscriber."""
        self._device_manager = device_manager

    def set_update_callback(self, callback: Callable[[EventMessage], Awaitable[None]]):
        """Capture the callback set by Home Assistant."""
        self._callback = callback

    async def start_async(self):
        """Return the fake device manager."""
        return self._device_manager

    async def async_get_device_manager(self) -> DeviceManager:
        """Return the fake device manager."""
        return self._device_manager

    def stop_async(self):
        """No-op to stop the subscriber."""
        return None

    async def async_receive_event(self, event_message: EventMessage):
        """Simulate a received pubsub message, invoked by tests."""
        # Update device state, then invoke HomeAssistant to refresh
        await self._device_manager.async_handle_event(event_message)
        await self._callback(event_message)


async def async_setup_sdm_platform(hass, platform, devices={}, structures={}):
    """Set up the platform and prerequisites."""
    MockConfigEntry(domain=DOMAIN, data=CONFIG_ENTRY_DATA).add_to_hass(hass)
    device_manager = FakeDeviceManager(devices=devices, structures=structures)
    subscriber = FakeSubscriber(device_manager)
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
    ), patch("homeassistant.components.nest.PLATFORMS", [platform]), patch(
        "homeassistant.components.nest.GoogleNestSubscriber", return_value=subscriber
    ):
        assert await async_setup_component(hass, DOMAIN, CONFIG)
        await hass.async_block_till_done()
    return subscriber

"""Common libraries for test setup."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Generator
import copy
from dataclasses import dataclass
from typing import Any

from google_nest_sdm.auth import AbstractAuth
from google_nest_sdm.device import Device
from google_nest_sdm.device_manager import DeviceManager
from google_nest_sdm.event import EventMessage
from google_nest_sdm.event_media import CachePolicy
from google_nest_sdm.google_nest_subscriber import GoogleNestSubscriber

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.components.nest import DOMAIN

# Typing helpers
type PlatformSetup = Callable[[], Awaitable[None]]
type YieldFixture[_T] = Generator[_T]

WEB_AUTH_DOMAIN = DOMAIN
APP_AUTH_DOMAIN = f"{DOMAIN}.installed"

PROJECT_ID = "some-project-id"
CLIENT_ID = "some-client-id"
CLIENT_SECRET = "some-client-secret"
CLOUD_PROJECT_ID = "cloud-id-9876"
SUBSCRIBER_ID = "projects/cloud-id-9876/subscriptions/subscriber-id-9876"
SUBSCRIPTION_NAME = "projects/cloud-id-9876/subscriptions/subscriber-id-9876"


@dataclass
class NestTestConfig:
    """Holder for integration configuration."""

    config_entry_data: dict[str, Any] | None = None
    credential: ClientCredential | None = None


# Exercises mode where all configuration is from the config flow
TEST_CONFIG_APP_CREDS = NestTestConfig(
    config_entry_data={
        "sdm": {},
        "project_id": PROJECT_ID,
        "cloud_project_id": CLOUD_PROJECT_ID,
        "subscriber_id": SUBSCRIBER_ID,
        "auth_implementation": "imported-cred",
    },
    credential=ClientCredential(CLIENT_ID, CLIENT_SECRET),
)
TEST_CONFIGFLOW_APP_CREDS = NestTestConfig(
    credential=ClientCredential(CLIENT_ID, CLIENT_SECRET),
)

TEST_CONFIG_NEW_SUBSCRIPTION = NestTestConfig(
    config_entry_data={
        "sdm": {},
        "project_id": PROJECT_ID,
        "cloud_project_id": CLOUD_PROJECT_ID,
        "subscription_name": SUBSCRIPTION_NAME,
        "auth_implementation": "imported-cred",
    },
    credential=ClientCredential(CLIENT_ID, CLIENT_SECRET),
)


class FakeSubscriber(GoogleNestSubscriber):
    """Fake subscriber that supplies a FakeDeviceManager."""

    stop_calls = 0

    def __init__(self) -> None:  # pylint: disable=super-init-not-called
        """Initialize Fake Subscriber."""
        self._device_manager = DeviceManager()
        self._subscriber_name = "fake-name"

    def set_update_callback(self, target: Callable[[EventMessage], Awaitable[None]]):
        """Capture the callback set by Home Assistant."""
        self._device_manager.set_update_callback(target)

    async def create_subscription(self):
        """Create the subscription."""
        return

    async def delete_subscription(self):
        """Delete the subscription."""
        return

    async def start_async(self):
        """Return the fake device manager."""
        return self._device_manager

    async def async_get_device_manager(self) -> DeviceManager:
        """Return the fake device manager."""
        return self._device_manager

    @property
    def cache_policy(self) -> CachePolicy:
        """Return the cache policy."""
        return self._device_manager.cache_policy

    def stop_async(self):
        """No-op to stop the subscriber."""
        self.stop_calls += 1

    async def async_receive_event(self, event_message: EventMessage):
        """Simulate a received pubsub message, invoked by tests."""
        # Update device state, then invoke HomeAssistant to refresh
        await self._device_manager.async_handle_event(event_message)


DEVICE_ID = "enterprise/project-id/devices/device-id"
DEVICE_COMMAND = f"{DEVICE_ID}:executeCommand"


class CreateDevice:
    """Fixture used for creating devices."""

    def __init__(
        self,
        device_manager: DeviceManager,
        auth: AbstractAuth,
    ) -> None:
        """Initialize CreateDevice."""
        self.device_manager = device_manager
        self.auth = auth
        self.data = {"traits": {}}

    def create(
        self,
        raw_traits: dict[str, Any] | None = None,
        raw_data: dict[str, Any] | None = None,
    ) -> None:
        """Create a new device with the specifeid traits."""
        data = copy.deepcopy(self.data)
        data.update(raw_data if raw_data else {})
        data["traits"].update(raw_traits if raw_traits else {})
        self.device_manager.add_device(Device.MakeDevice(data, auth=self.auth))

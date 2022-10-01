"""Common libraries for test setup."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Generator
import copy
from dataclasses import dataclass, field
import time
from typing import Any, TypeVar

from google_nest_sdm.auth import AbstractAuth
from google_nest_sdm.device import Device
from google_nest_sdm.device_manager import DeviceManager
from google_nest_sdm.event import EventMessage
from google_nest_sdm.event_media import CachePolicy
from google_nest_sdm.google_nest_subscriber import GoogleNestSubscriber

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.components.nest import DOMAIN
from homeassistant.components.nest.const import SDM_SCOPES

from tests.common import MockConfigEntry

# Typing helpers
PlatformSetup = Callable[[], Awaitable[None]]
_T = TypeVar("_T")
YieldFixture = Generator[_T, None, None]

WEB_AUTH_DOMAIN = DOMAIN
APP_AUTH_DOMAIN = f"{DOMAIN}.installed"

PROJECT_ID = "some-project-id"
CLIENT_ID = "some-client-id"
CLIENT_SECRET = "some-client-secret"
CLOUD_PROJECT_ID = "cloud-id-9876"
SUBSCRIBER_ID = "projects/cloud-id-9876/subscriptions/subscriber-id-9876"


CONFIG = {
    "nest": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "project_id": PROJECT_ID,
        "subscriber_id": SUBSCRIBER_ID,
    },
}

FAKE_TOKEN = "some-token"
FAKE_REFRESH_TOKEN = "some-refresh-token"


def create_token_entry(token_expiration_time=None):
    """Create OAuth 'token' data for a ConfigEntry."""
    if token_expiration_time is None:
        token_expiration_time = time.time() + 86400
    return {
        "access_token": FAKE_TOKEN,
        "refresh_token": FAKE_REFRESH_TOKEN,
        "scope": " ".join(SDM_SCOPES),
        "token_type": "Bearer",
        "expires_at": token_expiration_time,
    }


def create_config_entry(token_expiration_time=None) -> MockConfigEntry:
    """Create a ConfigEntry and add it to Home Assistant."""
    config_entry_data = {
        "sdm": {},  # Indicates new SDM API, not legacy API
        "auth_implementation": "nest",
        "token": create_token_entry(token_expiration_time),
    }
    return MockConfigEntry(domain=DOMAIN, data=config_entry_data)


@dataclass
class NestTestConfig:
    """Holder for integration configuration."""

    config: dict[str, Any] = field(default_factory=dict)
    config_entry_data: dict[str, Any] | None = None
    auth_implementation: str = WEB_AUTH_DOMAIN
    credential: ClientCredential | None = None


# Exercises mode where all configuration is in configuration.yaml
TEST_CONFIG_YAML_ONLY = NestTestConfig(
    config=CONFIG,
    config_entry_data={
        "sdm": {},
        "token": create_token_entry(),
    },
)
TEST_CONFIGFLOW_YAML_ONLY = NestTestConfig(
    config=TEST_CONFIG_YAML_ONLY.config,
)

# Exercises mode where subscriber id is created in the config flow, but
# all authentication is defined in configuration.yaml
TEST_CONFIG_HYBRID = NestTestConfig(
    config={
        "nest": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "project_id": PROJECT_ID,
        },
    },
    config_entry_data={
        "sdm": {},
        "token": create_token_entry(),
        "cloud_project_id": CLOUD_PROJECT_ID,
        "subscriber_id": SUBSCRIBER_ID,
    },
)
TEST_CONFIGFLOW_HYBRID = NestTestConfig(TEST_CONFIG_HYBRID.config)

# Exercises mode where all configuration is from the config flow
TEST_CONFIG_APP_CREDS = NestTestConfig(
    config_entry_data={
        "sdm": {},
        "token": create_token_entry(),
        "project_id": PROJECT_ID,
        "cloud_project_id": CLOUD_PROJECT_ID,
        "subscriber_id": SUBSCRIBER_ID,
    },
    auth_implementation="imported-cred",
    credential=ClientCredential(CLIENT_ID, CLIENT_SECRET),
)
TEST_CONFIGFLOW_APP_CREDS = NestTestConfig(
    config=TEST_CONFIG_APP_CREDS.config,
    auth_implementation="imported-cred",
    credential=ClientCredential(CLIENT_ID, CLIENT_SECRET),
)

TEST_CONFIG_LEGACY = NestTestConfig(
    config={
        "nest": {
            "client_id": "some-client-id",
            "client_secret": "some-client-secret",
        },
    },
    config_entry_data={
        "auth_implementation": "local",
        "tokens": {
            "expires_at": time.time() + 86400,
            "access_token": {
                "token": "some-token",
            },
        },
    },
)
TEST_CONFIG_ENTRY_LEGACY = NestTestConfig(
    config_entry_data={
        "auth_implementation": "local",
        "tokens": {
            "expires_at": time.time() + 86400,
            "access_token": {
                "token": "some-token",
            },
        },
    },
)


class FakeSubscriber(GoogleNestSubscriber):
    """Fake subscriber that supplies a FakeDeviceManager."""

    def __init__(self):
        """Initialize Fake Subscriber."""
        self._device_manager = DeviceManager()

    def set_update_callback(self, callback: Callable[[EventMessage], Awaitable[None]]):
        """Capture the callback set by Home Assistant."""
        self._device_manager.set_update_callback(callback)

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
        return None

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
        self, raw_traits: dict[str, Any] = None, raw_data: dict[str, Any] = None
    ) -> None:
        """Create a new device with the specifeid traits."""
        data = copy.deepcopy(self.data)
        data.update(raw_data if raw_data else {})
        data["traits"].update(raw_traits if raw_traits else {})
        self.device_manager.add_device(Device.MakeDevice(data, auth=self.auth))

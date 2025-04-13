"""Common libraries for test setup."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Generator
import copy
from dataclasses import dataclass
import re
from typing import Any

from google_nest_sdm.streaming_manager import Message

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.components.nest import DOMAIN
from homeassistant.components.nest.const import API_URL

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

DEVICE_ID = "enterprises/project-id/devices/device-id"
DEVICE_COMMAND = f"{DEVICE_ID}:executeCommand"
DEVICE_URL_MATCH = re.compile(
    f"{API_URL}/enterprises/project-id/devices/[^:]+:executeCommand"
)
TEST_IMAGE_URL = "https://domain/sdm_event_snapshot/dGTZwR3o4Y1..."
TEST_CLIP_URL = "https://domain/clip/XyZ.mp4"


class CreateDevice:
    """Fixture used for creating devices."""

    def __init__(self) -> None:
        """Initialize CreateDevice."""
        self.data = {"traits": {}}
        self.devices = []

    def create(
        self,
        raw_traits: dict[str, Any] | None = None,
        raw_data: dict[str, Any] | None = None,
    ) -> None:
        """Create a new device with the specifeid traits."""
        data = copy.deepcopy(self.data)
        data.update(raw_data if raw_data else {})
        data["traits"].update(raw_traits if raw_traits else {})
        self.devices.append(data)


def create_nest_event(data: dict[str, Any]) -> Message:
    """Create a pub/sub event message for testing."""
    return Message.from_data(data)

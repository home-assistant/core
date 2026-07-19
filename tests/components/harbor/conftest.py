"""Common fixtures for the Harbor tests."""

from collections.abc import Awaitable, Callable, Generator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.harbor.const import (
    CONF_CERT_PEM,
    CONF_KEY_PEM,
    CONF_SERIAL,
    DOMAIN,
)
from homeassistant.const import CONF_IP_ADDRESS

from tests.common import MockConfigEntry

SERIAL = "1234567890"
CERT_PEM = "-----BEGIN CERTIFICATE-----\nMIIBdummy\n-----END CERTIFICATE-----"
KEY_PEM = "-----BEGIN PRIVATE KEY-----\nMIIBdummy\n-----END PRIVATE KEY-----"

HEARTBEAT_TOPIC = f"cameras/{SERIAL}/events/heartbeat"
LIVEKIT_TOPIC = f"cameras/{SERIAL}/events/local_livekit_heartbeat"

HEARTBEAT_PAYLOAD: dict[str, Any] = {
    "temperature": 98.6,
    "os_version": "1.2.3",
    "settings": {"preference_display_name": "Nursery"},
}
LIVEKIT_PAYLOAD: dict[str, Any] = {
    "bitrate": 1234.5,
    "network_bars": 3,
    "stream_quality": "GOOD",
    "viewers_by_identity_full": {
        "viewer-1": {"identity": "alice"},
        "viewer-2": {"identity": "bob"},
    },
    "os_version": "1.2.3",
    "app_version": "4.5.6",
}


def connection_callback(
    mock_mqtt_client: AsyncMock,
) -> Callable[[bool], Awaitable[None]]:
    """Return the on_connection_change callback the integration registered."""
    return mock_mqtt_client.call_args.kwargs["on_connection_change"]


async def emit_message(
    mock_mqtt_client: AsyncMock, topic: str, payload: dict[str, Any]
) -> None:
    """Deliver an MQTT message through the handler the integration registered."""
    await mock_mqtt_client.call_args.kwargs["message_handler"](topic, payload)


async def set_connected(mock_mqtt_client: AsyncMock, connected: bool) -> None:
    """Drive the MQTT connection state the integration observes."""
    await connection_callback(mock_mqtt_client)(connected)


@pytest.fixture(autouse=True)
def mock_connect_timeout() -> Generator[None]:
    """Patch the connect timeout so unreachable-camera tests run quickly."""
    with patch("homeassistant.components.harbor.coordinator.CONNECT_TIMEOUT", 0):
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.harbor.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_mqtt_client() -> Generator[AsyncMock]:
    """Mock the Harbor MQTT client, reporting a successful connection on start."""
    with patch(
        "homeassistant.components.harbor.coordinator.HarborMQTTClient",
        autospec=True,
    ) as mock_client:

        async def _start() -> None:
            await set_connected(mock_client, True)
            # Setup waits for the first device message too; simulate the
            # initial-commands response landing right after connect, the
            # same way a real camera answers before any explicit test
            # message. Empty so it doesn't set values tests don't expect.
            await mock_client.call_args.kwargs["message_handler"](HEARTBEAT_TOPIC, {})

        mock_client.return_value.start.side_effect = _start
        # The config flow probes get-settings for the camera's friendly name;
        # default to an unnamed camera so the title falls back to the serial.
        mock_client.return_value.get_settings.return_value = SimpleNamespace(
            settings=SimpleNamespace(preference_display_name=None)
        )
        yield mock_client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock Harbor config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        title=f"Camera {SERIAL}",
        data={
            CONF_SERIAL: SERIAL,
            CONF_CERT_PEM: CERT_PEM,
            CONF_KEY_PEM: KEY_PEM,
            CONF_IP_ADDRESS: "192.168.1.10",
        },
    )

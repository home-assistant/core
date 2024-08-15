"""Test fixtures for mqtt component."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from random import getrandbits
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components import mqtt
from homeassistant.components.mqtt.models import MessageCallbackType, ReceiveMessage
from homeassistant.components.mqtt.util import EnsureJobAfterCooldown
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant, callback

from tests.common import MockConfigEntry
from tests.typing import MqttMockPahoClient

ENTRY_DEFAULT_BIRTH_MESSAGE = {
    mqtt.CONF_BROKER: "mock-broker",
    mqtt.CONF_BIRTH_MESSAGE: {
        mqtt.ATTR_TOPIC: "homeassistant/status",
        mqtt.ATTR_PAYLOAD: "online",
        mqtt.ATTR_QOS: 0,
        mqtt.ATTR_RETAIN: False,
    },
}


@pytest.fixture(autouse=True)
def patch_hass_config(mock_hass_config: None) -> None:
    """Patch configuration.yaml."""


@pytest.fixture
def temp_dir_prefix() -> str:
    """Set an alternate temp dir prefix."""
    return "test"


@pytest.fixture
def mock_temp_dir(temp_dir_prefix: str) -> Generator[str]:
    """Mock the certificate temp directory."""
    with patch(
        # Patch temp dir name to avoid tests fail running in parallel
        "homeassistant.components.mqtt.util.TEMP_DIR_NAME",
        f"home-assistant-mqtt-{temp_dir_prefix}-{getrandbits(10):03x}",
    ) as mocked_temp_dir:
        yield mocked_temp_dir


@pytest.fixture
def mock_debouncer(hass: HomeAssistant) -> Generator[asyncio.Event]:
    """Mock EnsureJobAfterCooldown.

    Returns an asyncio.Event that allows to await the debouncer task to be finished.
    """
    task_done = asyncio.Event()

    class MockDeboncer(EnsureJobAfterCooldown):
        """Mock the MQTT client (un)subscribe debouncer."""

        async def _async_job(self) -> None:
            """Execute after a cooldown period."""
            await super()._async_job()
            task_done.set()

    # We mock the import of EnsureJobAfterCooldown in client.py
    with patch(
        "homeassistant.components.mqtt.client.EnsureJobAfterCooldown", MockDeboncer
    ):
        yield task_done


@pytest.fixture
async def setup_with_birth_msg_client_mock(
    hass: HomeAssistant,
    mqtt_config_entry_data: dict[str, Any] | None,
    mqtt_client_mock: MqttMockPahoClient,
) -> AsyncGenerator[MqttMockPahoClient]:
    """Test sending birth message."""
    birth = asyncio.Event()
    with (
        patch("homeassistant.components.mqtt.client.INITIAL_SUBSCRIBE_COOLDOWN", 0.0),
        patch("homeassistant.components.mqtt.client.DISCOVERY_COOLDOWN", 0.0),
        patch("homeassistant.components.mqtt.client.SUBSCRIBE_COOLDOWN", 0.0),
    ):
        entry = MockConfigEntry(
            domain=mqtt.DOMAIN, data={mqtt.CONF_BROKER: "test-broker"}
        )
        entry.add_to_hass(hass)
        hass.config.components.add(mqtt.DOMAIN)
        assert await hass.config_entries.async_setup(entry.entry_id)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)

        @callback
        def wait_birth(msg: ReceiveMessage) -> None:
            """Handle birth message."""
            birth.set()

        await mqtt.async_subscribe(hass, "homeassistant/status", wait_birth)
        await hass.async_block_till_done()
        await birth.wait()
        yield mqtt_client_mock


@pytest.fixture
def recorded_calls() -> list[ReceiveMessage]:
    """Fixture to hold recorded calls."""
    return []


@pytest.fixture
def record_calls(recorded_calls: list[ReceiveMessage]) -> MessageCallbackType:
    """Fixture to record calls."""

    @callback
    def record_calls(msg: ReceiveMessage) -> None:
        """Record calls."""
        recorded_calls.append(msg)

    return record_calls

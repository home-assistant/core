"""Common fixtures for the Eurotronic Comet WiFi tests."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components import mqtt
from homeassistant.components.eurotronic_comet_wifi.const import DOMAIN
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant, callback

from . import (
    COMMAND_TOPIC_SETPOINT,
    MAC,
    PAYLOAD_AMBIENT_22,
    PAYLOAD_SETPOINT_21,
    REPLY_TOPIC_AMBIENT,
    REPLY_TOPIC_SETPOINT,
)

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import MqttMockHAClient


class FakeDevice:
    """A thermostat on the mocked broker that answers the integration's commands."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize fake device."""
        self.hass = hass
        self.online = True
        self.setpoint = PAYLOAD_SETPOINT_21
        self.ambient = PAYLOAD_AMBIENT_22

    @callback
    def on_command(self, msg: mqtt.ReceiveMessage) -> None:
        """Store setpoint and reply with current values."""
        if not self.online:
            return
        if msg.topic == COMMAND_TOPIC_SETPOINT and isinstance(msg.payload, str):
            self.setpoint = msg.payload
        async_fire_mqtt_message(self.hass, REPLY_TOPIC_SETPOINT, self.setpoint)
        async_fire_mqtt_message(self.hass, REPLY_TOPIC_AMBIENT, self.ambient)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.eurotronic_comet_wifi.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for the fake device."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Comet WiFi {MAC}",
        data={CONF_MAC: MAC},
        unique_id=MAC,
    )


@pytest.fixture
async def device(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> AsyncGenerator[FakeDevice]:
    """Put a fake thermostat on the broker and skip waiting for replies."""
    fake_device = FakeDevice(hass)
    unsubscribe = await mqtt.async_subscribe(
        hass, f"01/{MAC}/S/+", fake_device.on_command
    )
    with (
        patch(
            "homeassistant.components.eurotronic_comet_wifi.config_flow.FETCH_DATA_TIMEOUT",
            0,
        ),
        patch(
            "homeassistant.components.eurotronic_comet_wifi.coordinator.FETCH_DATA_TIMEOUT",
            0,
        ),
    ):
        yield fake_device
    unsubscribe()

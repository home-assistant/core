"""Common fixtures for the Happiest Baby Snoo tests."""

from collections.abc import Generator
import time
from unittest.mock import AsyncMock, patch

from pubnub.models.consumer.pubsub import PNMessageResult
import pytest
from python_snoo.containers import SnooDevice
from python_snoo.pubnub_async import SnooPubNub
from python_snoo.snoo import Snoo

from .const import MOCK_AMAZON_AUTH, MOCK_SNOO_AUTH, MOCK_SNOO_DEVICES


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.snoo.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


class MockedSnoo(Snoo):
    """Mock the Snoo object."""

    def __init__(self, email, password, clientsession) -> None:
        """Set up a Mocked Snoo."""
        super().__init__(email, password, clientsession)
        self.auth_error = None

    async def subscribe(self, device: SnooDevice, function):
        """Mock the subscribe function."""
        self.pubnub = AsyncMock()
        if device.serialNumber not in self.pubnub_instances:
            self.pubnub_instances[device.serialNumber] = SnooPubNub(
                self.pubnub, device.serialNumber
            )
        return self.pubnub_instances[device.serialNumber].subscribe(function)

    async def send_command(self, command: str, device: SnooDevice, **kwargs):
        """Mock the send command function."""
        if command == "send_status":
            # This is only called on first setup.
            await self.send_mock_message(
                device,
                message={
                    "system_state": "normal",
                    "sw_version": "v1.14.27",
                    "state_machine": {
                        "session_id": "0",
                        "state": "ONLINE",
                        "is_active_session": "false",
                        "since_session_start_ms": -1,
                        "time_left": -1,
                        "hold": "off",
                        "weaning": "off",
                        "audio": "on",
                        "up_transition": "NONE",
                        "down_transition": "NONE",
                        "sticky_white_noise": "off",
                    },
                    "left_safety_clip": 1,
                    "right_safety_clip": 1,
                    "event": "status_requested",
                    "event_time_ms": int(time.time()),
                    "rx_signal": {"rssi": -45, "strength": 100},
                },
            )
        return AsyncMock()

    async def authorize(self):
        """Do normal auth flow unless error is patched."""
        if self.auth_error:
            raise self.auth_error
        return await super().authorize()

    def set_auth_error(self, error: Exception | None):
        """Set an error for authentication."""
        self.auth_error = error

    async def auth_amazon(self):
        """Mock the amazon auth."""
        return MOCK_AMAZON_AUTH

    async def auth_snoo(self, id_token):
        """Mock the snoo auth."""
        return MOCK_SNOO_AUTH

    async def schedule_reauthorization(self, snoo_expiry: int):
        """Mock scheduling reauth."""
        return AsyncMock()

    async def get_devices(self) -> list[SnooDevice]:
        """Move getting devices."""
        return [SnooDevice.from_dict(dev) for dev in MOCK_SNOO_DEVICES]

    async def send_mock_message(self, device: SnooDevice, message: dict) -> None:
        """Send a fake message on the pubnub topic."""
        self.pubnub_instances[device.serialNumber].message(
            self.pubnub,
            PNMessageResult(
                subscription=None,
                publisher=None,
                channel=f"ActivityState.{device.serialNumber}",
                timetoken=int(time.time()),
                message=message,
            ),
        )


@pytest.fixture(name="bypass_api")
def bypass_api() -> MockedSnoo:
    """Bypass the Snoo api."""
    api = MockedSnoo("email", "password", AsyncMock())
    with (
        patch("homeassistant.components.snoo.Snoo", return_value=api),
        patch("homeassistant.components.snoo.config_flow.Snoo", return_value=api),
    ):
        yield api

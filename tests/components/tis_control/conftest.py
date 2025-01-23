"""Test fixtures for the TIS Control integration."""

from collections.abc import Iterable
from unittest.mock import MagicMock

import pytest

from homeassistant.components.tis_control.const import DEVICES_DICT, DOMAIN
from homeassistant.core import HomeAssistant


@pytest.fixture
def switch_factory():
    """Fixture to generate mock TISSwitch-compatible data."""

    def factory(
        name="Test Switch",
        device_id=None,
        channel_number=1,
        unique_id=None,
        is_protected=False,
        gateway="192.168.1.200",
    ) -> list[dict]:
        if device_id is None:
            device_id = [1, 48]
        entity = {
            "name": name,
            "device_id": device_id,
            "is_protected": is_protected,
            "gateway": gateway,
            "channels": [
                {
                    "channel_number": channel_number,
                    "channel_type": "output",
                    "channel_name": "Output Channel 1",
                }
            ],
        }
        if unique_id:
            entity["unique_id"] = f"switch_{name}"
        return [entity]

    return factory


@pytest.fixture
def async_add_devices() -> MagicMock:
    """Fixture to mock AddEntitiesCallback protocol."""
    mock = MagicMock(name="AddEntitiesCallbackMock")

    # Define the __call__ method on the mock
    def mock_call(
        new_entities: Iterable[Entity], update_before_add: bool = False
    ) -> None:
        pass  # Implement mock behavior here if needed

    mock.side_effect = mock_call

    return mock


class Entity:
    """place holder."""


class Protocol:
    """place holder."""


class Sender:
    """place holder."""


# create a mock class
class MockTISApi:
    """Mock TISApi class."""

    def __init__(
        self,
        hass: HomeAssistant,
        devices_dict: dict,
        host: str = "0.0.0.0",
        port: int = 6000,
        local_ip: str = "0.0.0.0",
        domain: str = DOMAIN,
        display_logo: str | None = "./custom_components/tis_control/",
    ) -> None:
        """Initialize the mock class."""
        self.host = host
        self.port = port
        self.local_ip = local_ip
        self.hass = hass
        self.domain = domain
        self.devices_dict = DEVICES_DICT
        self.display_logo = display_logo
        self.sender = Sender()
        self.sender.send_packet_with_ack = self.send_packet_with_ack
        self.protocol = Protocol()
        self.protocol.sender = self.sender

    async def connect(self) -> None:
        """Mock connect."""

    async def get_entities(self) -> list:
        """Mock get_entities."""

    async def send_packet_with_ack(
        self,
        packet,
        attempts: int = 10,
        timeout: float = 0.5,
        debounce_time: float = 0.5,  # The debounce time in seconds
    ) -> None:
        """Mock send_packet_with_ack."""

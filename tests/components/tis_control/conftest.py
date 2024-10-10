"""Common fixtures for the TISControl tests."""

from collections.abc import Generator, Iterable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.tis_control.const import DEVICES_DICT, DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.tis_control.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        mock_setup_entry.data = {"port": "6000"}
        mock_setup_entry.domain = DOMAIN
        mock_setup_entry.entry_id = "1234"
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="CN11A1A00001",
        domain=DOMAIN,
        data={
            "port": "6000",
        },
        unique_id="CN11A1A00001",
    )


@pytest.fixture
def switch_factory():
    """Fixture to generate mock TISSwitch instances."""

    def factory(**kwargs) -> list[dict]:
        # Create a new MagicMock instance for each call
        return [
            {
                kwargs.get("name"): {
                    "device_id": kwargs.get("device_id"),
                    "appliance_type": "switch",
                    "appliance_class": "",
                    "is_protected": False,
                    "gateway": "192.168.1.200",
                    "channels": [
                        {
                            "channel_number": kwargs.get("channel_number"),
                            "channel_type": "output",
                            "channel_name": "Output Channel 1",
                        }
                    ],
                }
            },
        ]

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
        destination: str,
        packet: list,
        packet_dict=None,
        channel_number=None,
        attempts: int = 10,
        timeout: float = 0.5,
        debounce_time: float = 0.5,
    ) -> None:
        """Mock send_packet_with_ack."""

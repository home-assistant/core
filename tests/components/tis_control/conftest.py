"""Common fixtures for the TIS Control tests."""

from collections.abc import Callable, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tis_smartbus import DiscoveredDevice, Telegram, lookup

from homeassistant.components.tis_control.const import DOMAIN
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry

HOST = "192.168.1.50"

DEVICES = [
    {
        "subnet": 1,
        "device": 5,
        "channel": channel,
        "module": "Living Dimmer",
        "model": "DIM-6CH-2A",
    }
    for channel in (1, 2)
]


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.tis_control.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for one dimmer with two channels."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01K74TISCONTROLTESTENTRY01",
        title=f"TIS gateway {HOST}",
        unique_id=f"{HOST}:6000",
        data={CONF_HOST: HOST, CONF_PORT: 6000, CONF_DEVICES: DEVICES},
    )


@pytest.fixture
def mock_gateway() -> Generator[MagicMock]:
    """Mock the TIS gateway: a 6-channel dimmer at 1.5 and an HVAC module at 1.10."""
    with (
        patch(
            "homeassistant.components.tis_control.TISGateway", autospec=True
        ) as gateway_class,
        patch(
            "homeassistant.components.tis_control.config_flow.TISGateway",
            new=gateway_class,
        ),
    ):
        gateway = gateway_class.return_value
        gateway.discover.return_value = [
            DiscoveredDevice(1, 5, lookup(0x0258), "Living Dimmer"),
            DiscoveredDevice(1, 10, lookup(0x0077), ""),
        ]
        levels: dict[tuple[int, int], list[int]] = {(1, 5): [100, 0, 40, 0, 0, 0]}
        gateway.levels = levels

        async def read_channels(
            subnet: int, device: int, timeout: float = 2.0
        ) -> list[int] | None:
            return levels.get((subnet, device))

        gateway.read_channels.side_effect = read_channels

        listeners: list[Callable[[Telegram], None]] = []

        def add_listener(listener: Callable[[Telegram], None]) -> Callable[[], None]:
            listeners.append(listener)
            return lambda: listeners.remove(listener)

        gateway.add_listener.side_effect = add_listener

        def push(source: tuple[int, int], opcode: int, content: bytes) -> None:
            telegram = Telegram(*source, 0x0258, opcode, 255, 255, content, True)
            for listener in listeners:
                listener(telegram)

        gateway.push = push
        yield gateway

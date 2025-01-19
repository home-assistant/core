"""Common fixtures for the Happiest Baby Snoo tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from python_snoo.containers import SnooDevice
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
        return AsyncMock()

    async def send_command(self, command: str, device: SnooDevice, **kwargs):
        """Mock the send command function."""
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


@pytest.fixture(name="bypass_api")
def bypass_api() -> MockedSnoo:
    """Bypass the Snoo api."""
    api = MockedSnoo("email", "password", AsyncMock())
    with (
        patch("homeassistant.components.snoo.Snoo", return_value=api),
        patch("homeassistant.components.snoo.config_flow.Snoo", return_value=api),
    ):
        yield api

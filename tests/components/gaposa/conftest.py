"""Common fixtures for the Gaposa tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pygaposa import Client, Device, Gaposa, Motor
from pygaposa.client import User
import pytest

from homeassistant.components.gaposa.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "test-password"
TEST_API_KEY = "test-apikey"
TEST_DEVICE_SERIAL = "DEVICE123"
TEST_CLIENT_ID = "gaposa-client-123"
TEST_USER_UID = "firebase-uid-test-1234"


def _make_mock_motor(motor_id: str, name: str, state: str = "UP") -> MagicMock:
    """Return a MagicMock shaped like a pygaposa Motor."""
    motor = MagicMock(spec=Motor)
    motor.id = motor_id
    motor.name = name
    motor.state = state
    motor.up = AsyncMock()
    motor.down = AsyncMock()
    motor.stop = AsyncMock()
    motor.update = AsyncMock()
    return motor


def _make_mock_device(serial: str, motors: list[MagicMock]) -> MagicMock:
    """Return a MagicMock shaped like a pygaposa Device."""
    device = MagicMock(spec=Device)
    device.serial = serial
    device.motors = motors
    return device


def _make_mock_client(devices: list[MagicMock], client_id: str) -> MagicMock:
    """Return a MagicMock shaped like a pygaposa Client."""
    client = MagicMock(spec=Client)
    client.id = client_id
    client.devices = devices
    return client


@pytest.fixture
def mock_motors() -> list[MagicMock]:
    """Two motors: Living Room (open) and Bedroom (closed)."""
    return [
        _make_mock_motor("motor-1", "Living Room", state="UP"),
        _make_mock_motor("motor-2", "Bedroom", state="DOWN"),
    ]


@pytest.fixture
def mock_gaposa(mock_motors: list[MagicMock]) -> Generator[MagicMock]:
    """Patch pygaposa.Gaposa and yield the shared mocked instance.

    The Gaposa class is imported at module load time in both the
    coordinator and config flow, so both have to be patched.
    """
    device = _make_mock_device(TEST_DEVICE_SERIAL, mock_motors)
    client = _make_mock_client([device], TEST_CLIENT_ID)
    user = MagicMock(spec=User)
    user.uid = TEST_USER_UID
    instance = MagicMock(spec=Gaposa)
    instance.login = AsyncMock()
    instance.update = AsyncMock()
    instance.close = AsyncMock()
    instance.clients = [(client, user)]
    with (
        patch(
            "homeassistant.components.gaposa.coordinator.Gaposa",
            return_value=instance,
        ),
        patch(
            "homeassistant.components.gaposa.config_flow.Gaposa",
            return_value=instance,
        ),
    ):
        yield instance


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry for config-flow tests."""
    with patch(
        "homeassistant.components.gaposa.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: TEST_API_KEY,
            CONF_USERNAME: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
        title="Gaposa Gateway",
        unique_id=TEST_USER_UID,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gaposa: MagicMock,
) -> MockConfigEntry:
    """Add the config entry to hass and run through a real setup."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry

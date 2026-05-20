"""Common fixtures for the Gaposa tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pygaposa import Motor
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
    device = MagicMock()
    device.serial = serial
    device.motors = motors
    device.addListener = MagicMock()
    device.removeListener = MagicMock()
    return device


def _make_mock_client(devices: list[MagicMock], client_id: str) -> MagicMock:
    """Return a MagicMock shaped like a pygaposa Client."""
    client = MagicMock()
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
def mock_gaposa_instance(mock_motors: list[MagicMock]) -> MagicMock:
    """Return a mocked Gaposa client instance populated with test data."""
    device = _make_mock_device(TEST_DEVICE_SERIAL, mock_motors)
    client = _make_mock_client([device], TEST_CLIENT_ID)
    user = MagicMock()

    instance = MagicMock()
    instance.login = AsyncMock()
    instance.update = AsyncMock()
    instance.close = AsyncMock()
    instance.clients = [(client, user)]
    return instance


@pytest.fixture
def mock_gaposa(
    mock_gaposa_instance: MagicMock,
) -> Generator[MagicMock]:
    """Patch pygaposa.Gaposa in the coordinator and config flow modules.

    Both locations import Gaposa at module load time, so both have to be
    patched. Tests consume the shared ``mock_gaposa_instance`` via the
    fixture above — they don't need to drill through the class mock.
    """
    with (
        patch(
            "homeassistant.components.gaposa.coordinator.Gaposa",
            return_value=mock_gaposa_instance,
        ) as mock_class,
        patch(
            "homeassistant.components.gaposa.config_flow.Gaposa",
            return_value=mock_gaposa_instance,
        ),
    ):
        yield mock_class


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry and async_unload_entry for config-flow tests.

    Config flow tests care about the flow result and the data that ends up
    on the created entry — they should not exercise the real coordinator
    setup. Mocking unload too keeps HA's teardown path happy (the real
    async_unload_entry assumes runtime_data is populated).
    """
    with (
        patch(
            "homeassistant.components.gaposa.async_setup_entry", return_value=True
        ) as mock_setup,
        patch("homeassistant.components.gaposa.async_unload_entry", return_value=True),
    ):
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
        unique_id=TEST_CLIENT_ID,
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

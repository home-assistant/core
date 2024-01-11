"""Common fixtures for the Husqvarna Automower Bluetooth tests."""

from collections.abc import Awaitable, Callable, Generator
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.husqvarna_automower_ble.const import DOMAIN
from homeassistant.components.husqvarna_automower_ble.coordinator import SCAN_INTERVAL
from homeassistant.const import CONF_ADDRESS, CONF_CLIENT_ID
from homeassistant.core import HomeAssistant

from . import AUTOMOWER_SERVICE_INFO

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """Create hass config fixture."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: AUTOMOWER_SERVICE_INFO.address,
            CONF_CLIENT_ID: 1197489078,
        },
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.husqvarna_automower_ble.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def scan_step(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> Generator[None, None, Callable[[], Awaitable[None]]]:
    """Step system time forward."""

    freezer.move_to("2023-01-01T01:00:00Z")

    async def delay() -> None:
        """Trigger delay in system."""
        freezer.tick(delta=SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    return delay


class MockMower:
    """Mock BleakClient."""

    def __init__(self, *args, **kwargs) -> None:
        """Mock BleakClient."""

    async def __aexit__(self, *args, **kwargs):
        """Mock BleakClient.__aexit__."""

    async def connect(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        return True

    async def disconnect(self, *args, **kwargs):
        """Mock BleakClient.disconnect."""

    def is_connected(self):
        """Mock BleakClient.is_connected."""
        return True

    async def get_model(self) -> str:
        """Mock BleakClient.get_model."""
        return "305"

    async def battery_level(self) -> int:
        """Mock BleakClient.battery_level."""
        return 100

    async def mower_state(self) -> str:
        """Mock BleakClient.mower_state."""
        return "pendingStart"

    async def mower_activity(self) -> str:
        """Mock BleakClient.mower_activity."""
        return "charging"

    async def probe_gatts(self, device):
        """Mock BleakClient.probe_gatts."""
        return ("Husqvarna", "Automower", "305")


@pytest.fixture(autouse=True)
def mock_client(enable_bluetooth: None, scan_step) -> None:
    """Auto mock bluetooth."""

    with (
        patch(
            "homeassistant.components.husqvarna_automower_ble.config_flow.Mower",
            MockMower,
        ),
        patch("homeassistant.components.husqvarna_automower_ble.Mower", MockMower),
    ):
        yield MockMower

"""Common fixtures for the Husqvarna Automower Bluetooth tests."""
from collections.abc import Awaitable, Callable, Generator
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.husqvarna_automower_ble.const import DOMAIN
from homeassistant.components.husqvarna_automower_ble.coordinator import SCAN_INTERVAL
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from . import AUTOMOWER_SERVICE_INFO

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def mock_entry():
    """Create hass config fixture."""
    return MockConfigEntry(
        domain=DOMAIN, data={CONF_ADDRESS: AUTOMOWER_SERVICE_INFO.address}
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

    async def delay():
        """Trigger delay in system."""
        freezer.tick(delta=SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    return delay


class MockMower:
    """Mock BleakClient."""

    def __init__(self, *args, **kwargs):
        """Mock BleakClient."""

    async def __aexit__(self, *args, **kwargs):
        """Mock BleakClient.__aexit__."""

    async def connect(self, *args, **kwargs) -> bool:
        """Mock BleakClient.connect."""
        return True

    async def disconnect(self, *args, **kwargs):
        """Mock BleakClient.disconnect."""

    async def get_model(self) -> str:
        """Mock BleakClient.get_model."""
        return "305"

    async def probe_gatts(self, device):
        """Mock BleakClient.probe_gatts."""
        return ("Husqvarna", "Automower", "305")


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth):
    """Auto mock bluetooth."""

    with patch(
        "homeassistant.components.husqvarna_automower_ble.config_flow.Mower", MockMower
    ) and patch("homeassistant.components.husqvarna_automower_ble.Mower", MockMower):
        yield

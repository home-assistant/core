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
def mock_setup_entry() -> Generator[AsyncMock]:
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


@pytest.fixture(autouse=True)
def mock_automower_client(enable_bluetooth: None, scan_step) -> Generator[AsyncMock]:
    """Mock a BleakClient client."""
    with (
        patch(
            "homeassistant.components.husqvarna_automower_ble.Mower",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.husqvarna_automower_ble.config_flow.Mower",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.connect.return_value = True
        client.is_connected.return_value = True
        client.get_model.return_value = "305"
        client.battery_level.return_value = 100
        client.mower_state.return_value = "pendingStart"
        client.mower_activity.return_value = "charging"
        client.probe_gatts.return_value = ("Husqvarna", "Automower", "305")

        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Husqvarna AutoMower",
        data={
            CONF_ADDRESS: AUTOMOWER_SERVICE_INFO.address,
            CONF_CLIENT_ID: 1197489078,
        },
        unique_id=AUTOMOWER_SERVICE_INFO.address,
    )

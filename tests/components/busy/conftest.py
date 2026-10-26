"""BUSY Bar test fixtures."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from busylib import AsyncBusyBar, types
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from . import DEVICE_ID, HOST, MAC


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    """Provide a client with typed device responses."""
    client = AsyncMock(spec=AsyncBusyBar)
    client.__aenter__.return_value = client
    client.base_url = f"http://{HOST}"
    client.access.return_value = types.HttpAccessInfo(mode="enabled")
    client.access_token_mint.return_value = types.AccessToken(
        token="12345678-token",
        short_id="12345678",
        display_id="1234",
        name="Home Assistant",
        created_at=0,
        last_used_at=0,
    )
    client.status_device.return_value = types.StatusDevice(usb_mac=MAC)
    client.status.return_value = types.Status(
        device=types.StatusDevice(serial_number="BUSY123", otp_model="BB.1"),
        firmware=types.StatusFirmware(version="1.0", branch="release"),
        power=types.StatusPower(battery_charge=82),
    )
    client.wifi_status.return_value = types.StatusResponse(
        state=types.WifiState.CONNECTED, ssid="Home", rssi=-48
    )
    with (
        patch(
            "homeassistant.components.busy.config_flow.AsyncBusyBar",
            return_value=client,
        ),
        patch("homeassistant.components.busy.AsyncBusyBar", return_value=client),
        patch(
            "homeassistant.components.busy.coordinator.AsyncBusyBar",
            return_value=client,
        ),
    ):
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Provide a paired bar."""
    return MockConfigEntry(
        domain="busy",
        unique_id=DEVICE_ID,
        title="BUSY Bar",
        data={"host": HOST, "token": "12345678-token"},
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the sensor platform with a paired bar."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Isolate config flows from platform setup."""
    with patch(
        "homeassistant.components.busy.async_setup_entry", return_value=None
    ) as setup:
        yield setup

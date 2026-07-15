"""Common fixtures for the WATERCryst BIOCAT tests."""

from collections.abc import AsyncGenerator, Generator
from datetime import datetime
from unittest.mock import AsyncMock, patch

from pyocat.models import (
    DeviceResponse,
    EventResponse,
    ModeResponse,
    StateResponse,
    WaterProtectionResponse,
)
import pytest

from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.watercryst.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def mock_api_client(hass: HomeAssistant) -> AsyncGenerator[AsyncMock]:
    """Mock WATERCryst Smart Home client."""
    with patch(
        "homeassistant.components.watercryst.config_flow.AsyncApiClient"
    ) as mock:
        client = mock.return_value

        info = DeviceResponse(
            biocat_serial="2025001395300149",
            electronics_serial="2041730218",
            device_type_number="12000273",
            line="BIOCAT",
            series="KLS 3000-C",
            name="Schulungsgerät",
            current_firmware_version="V01.05.07",
            current_hardware_version="2",
            latest_firmware_version="V01.08.05",
            system_mac_address="00:A2:FF:01:EE:DE",
            ble_mac_address="CC:F9:57:8F:EE:C4",
        )

        client.get_device_info = AsyncMock(return_value=info)

        state = StateResponse(
            online=True,
            mode=ModeResponse(id="WT", name="Water Treatment"),
            event=EventResponse(
                type="event",
                event_id=0,
                category="info",
                title="Unknown Event",
                description="Unknown Event",
                timestamp=datetime(2026, 6, 8, 13, 13),
            ),
            water_protection=WaterProtectionResponse(
                absence_mode_enabled=False,
                pause_leakage_protection_until_utc=datetime(2026, 6, 8, 13, 13),
            ),
            ml_state="success",
        )

        client.get_state = AsyncMock(return_value=state)

        yield client

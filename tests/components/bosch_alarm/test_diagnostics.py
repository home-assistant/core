"""Test the Bosch Alarm diagnostics."""

from typing import Any
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_panel: AsyncMock,
    area: AsyncMock,
    model_name: str,
    serial_number: str,
    mock_config_entry: MockConfigEntry,
    config_flow_data: dict[str, Any],
) -> None:
    """Test generating diagnostics for bosch alarm."""
    await setup_integration(hass, mock_config_entry)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
    assert diag == {
        "data": {
            "areas": [
                {
                    "alarms": [],
                    "all_armed": False,
                    "all_ready": True,
                    "armed": False,
                    "arming": False,
                    "disarmed": True,
                    "faults": [],
                    "id": 1,
                    "name": "Area1",
                    "part_armed": False,
                    "part_ready": True,
                    "pending": False,
                    "triggered": False,
                },
            ],
            "doors": [
                {
                    "id": 1,
                    "locked": True,
                    "name": "Main Door",
                    "open": False,
                },
            ],
            "firmware_version": "1.0.0",
            "history_events": [],
            "model": model_name,
            "outputs": [
                {
                    "active": False,
                    "id": 1,
                    "name": "Output A",
                },
            ],
            "points": [
                {
                    "id": 0,
                    "name": "Window",
                    "normal": True,
                    "open": False,
                },
                {
                    "id": 1,
                    "name": "Door",
                    "normal": True,
                    "open": False,
                },
                {
                    "id": 2,
                    "name": "Motion Detector",
                    "normal": True,
                    "open": False,
                },
                {
                    "id": 3,
                    "name": "CO Detector",
                    "normal": True,
                    "open": False,
                },
                {
                    "id": 4,
                    "name": "Smoke Detector",
                    "normal": True,
                    "open": False,
                },
                {
                    "id": 5,
                    "name": "Glassbreak Sensor",
                    "normal": True,
                    "open": False,
                },
                {
                    "id": 6,
                    "name": "Bedroom",
                    "normal": True,
                    "open": False,
                },
            ],
            "protocol_version": "1.0.0",
            "serial_number": serial_number,
        },
        "entry_data": {
            "host": "0.0.0.0",
            "model": model_name,
            "port": 7700,
            **dict.fromkeys(config_flow_data, "**REDACTED**"),
        },
    }

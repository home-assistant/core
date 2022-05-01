"""Test Sensibo diagnostics."""
from __future__ import annotations

from unittest.mock import patch

import aiohttp

from homeassistant.core import HomeAssistant

from . import init_integration
from .response import DATA_FROM_API

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_diagnostics(hass: HomeAssistant, hass_client: aiohttp.client):
    """Test generating diagnostics for a config entry."""
    entry = await init_integration(hass, entry_id="halldiag")
    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=DATA_FROM_API,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diag == {
        "status": "success",
        "result": [
            {
                "id": "**REDACTED**",
                "qrId": "**REDACTED**",
                "room": {"uid": "**REDACTED**", "name": "Hallway", "icon": "Lounge"},
                "acState": {
                    "timestamp": {
                        "time": "2022-04-30T19:58:15.544787Z",
                        "secondsAgo": 0,
                    },
                    "on": False,
                    "mode": "fan",
                    "fanLevel": "high",
                    "swing": "stopped",
                    "horizontalSwing": "stopped",
                    "light": "on",
                },
                "location": "**REDACTED**",
                "accessPoint": {"ssid": "**REDACTED**", "password": None},
                "macAddress": "**REDACTED**",
                "autoOffMinutes": None,
                "autoOffEnabled": False,
                "antiMoldTimer": None,
                "antiMoldConfig": None,
            }
        ],
    }

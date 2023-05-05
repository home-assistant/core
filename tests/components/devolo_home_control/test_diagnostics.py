"""Tests for the devolo Home Control diagnostics."""
from __future__ import annotations

from unittest.mock import patch

from aiohttp import ClientSession

from homeassistant.components.devolo_home_control.diagnostics import TO_REDACT
from homeassistant.components.diagnostics import REDACTED
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import configure_integration
from .mocks import HomeControlMock, HomeControlMockBinarySensor

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(hass: HomeAssistant, hass_client: ClientSession):
    """Test setup and state change of a climate device."""
    entry = configure_integration(hass)
    gateway_1 = HomeControlMockBinarySensor()
    gateway_2 = HomeControlMock()
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[gateway_1, gateway_2],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state == ConfigEntryState.LOADED

        entry_dict = entry.as_dict()
        for key in TO_REDACT:
            entry_dict["data"][key] = REDACTED

        result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

        assert result == {
            "entry": entry_dict,
            "device_info": [
                {
                    "gateway": {
                        "local_connection": gateway_1.gateway.local_connection,
                        "firmware_version": gateway_1.gateway.firmware_version,
                    },
                    "devices": [
                        {
                            "device_id": device_id,
                            "device_model_uid": properties.device_model_uid,
                            "device_type": properties.device_type,
                            "name": properties.name,
                        }
                        for device_id, properties in gateway_1.devices.items()
                    ],
                },
                {
                    "gateway": {
                        "local_connection": gateway_2.gateway.local_connection,
                        "firmware_version": gateway_2.gateway.firmware_version,
                    },
                    "devices": [],
                },
            ],
        }

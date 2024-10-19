"""Tests for Comelit Simplehome diagnostics platform."""

from __future__ import annotations

from unittest.mock import patch

from aiocomelit.const import (
    BRIDGE,
    CLIMATE,
    COVER,
    IRRIGATION,
    LIGHT,
    OTHER,
    SCENARIO,
    WATT,
)

from homeassistant.components.comelit.const import DOMAIN
from homeassistant.components.comelit.diagnostics import TO_REDACT
from homeassistant.components.diagnostics import REDACTED
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_TYPE
from homeassistant.core import HomeAssistant

from .const import DEVICE_QUERY, MOCK_USER_BRIDGE_DATA

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test config entry diagnostics."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_BRIDGE_DATA)
    entry.add_to_hass(hass)

    with (
        patch("aiocomelit.api.ComeliteSerialBridgeApi.login"),
        patch(
            "aiocomelit.api.ComeliteSerialBridgeApi.get_all_devices",
            return_value=DEVICE_QUERY,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED

    entry_dict = entry.as_dict()
    for key in TO_REDACT:
        entry_dict["data"][key] = REDACTED
    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    coordinator = hass.data[DOMAIN][entry.entry_id]

    assert result == {
        "entry": entry_dict,
        "type": entry.data.get(CONF_TYPE, BRIDGE),
        "device_info": {
            "last_update success": coordinator.last_update_success,
            "last_exception": repr(coordinator.last_exception),
            "devices": [
                {
                    CLIMATE: [],
                },
                {
                    COVER: [
                        {
                            "0": {
                                "name": "Cover0",
                                "status": 0,
                                "human_status": "closed",
                                "protected": 0,
                                "val": 0,
                                "zone": "Open space",
                                "power": 0.0,
                                "power_unit": WATT,
                            },
                        }
                    ],
                },
                {
                    LIGHT: [
                        {
                            "0": {
                                "name": "Light0",
                                "status": 0,
                                "human_status": "off",
                                "protected": 0,
                                "val": 0,
                                "zone": "Bathroom",
                                "power": 0.0,
                                "power_unit": WATT,
                            }
                        }
                    ],
                },
                {
                    OTHER: [],
                },
                {
                    IRRIGATION: [],
                },
                {
                    SCENARIO: [],
                },
            ],
        },
    }

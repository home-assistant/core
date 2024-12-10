"""Tests for the diagnostics data provided by Switcher."""

import pytest

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from . import init_integration
from .consts import DUMMY_WATER_HEATER_DEVICE

from tests.common import ANY
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_bridge,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test diagnostics."""
    entry = await init_integration(hass)
    device = DUMMY_WATER_HEATER_DEVICE
    monkeypatch.setattr(device, "last_data_update", "2022-09-28T16:42:12.706017")
    mock_bridge.mock_callbacks([device])
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == {
        "devices": [
            {
                "auto_shutdown": "02:00:00",
                "device_id": REDACTED,
                "device_key": REDACTED,
                "device_state": {
                    "__type": "<enum 'DeviceState'>",
                    "repr": "<DeviceState.ON: ('01', 'on')>",
                },
                "device_type": {
                    "__type": "<enum 'DeviceType'>",
                    "repr": (
                        "<DeviceType.V4: ('Switcher V4', '0317', "
                        "1, <DeviceCategory.WATER_HEATER: 1>, False)>"
                    ),
                },
                "electric_current": 12.8,
                "ip_address": REDACTED,
                "last_data_update": "2022-09-28T16:42:12.706017",
                "mac_address": REDACTED,
                "name": "Heater FE12",
                "power_consumption": 2780,
                "remaining_time": "01:29:32",
                "token_needed": False,
            }
        ],
        "entry": {
            "entry_id": entry.entry_id,
            "version": 1,
            "minor_version": 1,
            "domain": "switcher_kis",
            "title": "Mock Title",
            "data": {},
            "options": {},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "unique_id": "switcher_kis",
            "disabled_by": None,
            "created_at": ANY,
            "modified_at": ANY,
            "discovery_keys": {},
            "subentries": [],
        },
    }

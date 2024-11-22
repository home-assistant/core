"""Tests for the diagnostics data provided by LG webOS Smart TV."""

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from . import setup_webostv

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, client
) -> None:
    """Test diagnostics."""
    entry = await setup_webostv(hass)
    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == {
        "client": {
            "is_registered": True,
            "is_connected": True,
            "current_app_id": "com.webos.app.livetv",
            "current_channel": {
                "channelId": "ch1id",
                "channelName": "Channel 1",
                "channelNumber": "1",
            },
            "apps": {
                "com.webos.app.livetv": {
                    "icon": REDACTED,
                    "id": "com.webos.app.livetv",
                    "largeIcon": REDACTED,
                    "title": "Live TV",
                }
            },
            "inputs": {
                "in1": {"appId": "app0", "id": "in1", "label": "Input01"},
                "in2": {"appId": "app1", "id": "in2", "label": "Input02"},
            },
            "system_info": {"modelName": "TVFAKE"},
            "software_info": {"major_ver": "major", "minor_ver": "minor"},
            "hello_info": {"deviceUUID": "**REDACTED**"},
            "sound_output": "speaker",
            "is_on": True,
        },
        "entry": {
            "entry_id": entry.entry_id,
            "version": 1,
            "minor_version": 1,
            "domain": "webostv",
            "title": "fake_webos",
            "data": {
                "client_secret": "**REDACTED**",
                "host": "**REDACTED**",
            },
            "options": {},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "unique_id": REDACTED,
            "disabled_by": None,
            "created_at": entry.created_at.isoformat(),
            "modified_at": entry.modified_at.isoformat(),
            "discovery_keys": {},
        },
    }

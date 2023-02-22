"""Test ONVIF diagnostics."""
from homeassistant.core import HomeAssistant

from . import (
    FIRMWARE_VERSION,
    MAC,
    MANUFACTURER,
    MODEL,
    SERIAL_NUMBER,
    setup_onvif_integration,
)

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test generating diagnostics for a config entry."""

    entry, _, _ = await setup_onvif_integration(hass)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diag == {
        "config": {
            "entry_id": "1",
            "version": 1,
            "domain": "onvif",
            "title": "Mock Title",
            "data": {
                "name": "TestCamera",
                "host": "**REDACTED**",
                "port": 80,
                "username": "**REDACTED**",
                "password": "**REDACTED**",
                "snapshot_auth": "digest",
            },
            "options": {"extra_arguments": "-pred 1", "rtsp_transport": "tcp"},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "unique_id": "aa:bb:cc:dd:ee",
            "disabled_by": None,
        },
        "device": {
            "info": {
                "manufacturer": MANUFACTURER,
                "model": MODEL,
                "fw_version": FIRMWARE_VERSION,
                "serial_number": SERIAL_NUMBER,
                "mac": MAC,
            },
            "capabilities": {
                "snapshot": False,
                "events": False,
                "ptz": False,
                "imaging": True,
            },
            "profiles": [
                {
                    "index": 0,
                    "token": "dummy",
                    "name": "profile1",
                    "video": None,
                    "ptz": None,
                    "video_source_token": None,
                }
            ],
        },
    }

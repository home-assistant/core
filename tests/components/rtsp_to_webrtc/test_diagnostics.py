"""Test nest diagnostics."""

from typing import Any

from .conftest import ComponentSetup

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry

THERMOSTAT_TYPE = "sdm.devices.types.THERMOSTAT"


async def test_entry_diagnostics(
    hass,
    hass_client,
    config_entry: MockConfigEntry,
    rtsp_to_webrtc_client: Any,
    setup_integration: ComponentSetup,
):
    """Test config entry diagnostics."""
    await setup_integration()

    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "discovery": {"attempt": 1, "web.failure": 1, "webrtc.success": 1},
        "web": {},
        "webrtc": {},
    }

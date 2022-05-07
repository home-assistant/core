"""Test TotalConnect diagnostics."""

from homeassistant.components.diagnostics import REDACTED

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.components.totalconnect.common import (
    DEVICE_INFO_BASIC_1,
    LOCATION_ID,
    init_integration,
)


async def test_entry_diagnostics(hass, hass_client):
    """Test config entry diagnostics."""
    entry = await init_integration(hass)

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    location = result["locations"][LOCATION_ID]
    assert location["location_id"] == LOCATION_ID

    device = location["devices"][DEVICE_INFO_BASIC_1["DeviceID"]]
    assert device["serial_number"] == REDACTED

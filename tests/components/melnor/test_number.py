"""Test the Melnor sensors."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from .conftest import (
    mock_config_entry,
    patch_async_ble_device_from_address,
    patch_async_register_callback,
    patch_melnor_device,
)


async def test_manual_watering_minutes(hass: HomeAssistant) -> None:
    """Test the manual watering switch."""

    entry = mock_config_entry(hass)

    with patch_async_ble_device_from_address(), patch_melnor_device() as device_patch, patch_async_register_callback():
        device = device_patch.return_value

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        number = hass.states.get("number.zone_1_manual_minutes")

        assert number.state == "0"
        assert number.attributes["max"] == 360
        assert number.attributes["min"] == 1
        assert number.attributes["step"] == 1.0
        assert number.attributes["icon"] == "mdi:timer-cog-outline"

        assert device.zone1.manual_watering_minutes == 0

        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": "number.zone_1_manual_minutes", "value": 10},
            blocking=True,
        )

        number = hass.states.get("number.zone_1_manual_minutes")

        assert number.state == "10"
        assert device.zone1.manual_watering_minutes == 10

"""Test the Melnor time platform."""
from __future__ import annotations

from datetime import time

from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from .conftest import (
    mock_config_entry,
    patch_async_ble_device_from_address,
    patch_async_register_callback,
    patch_melnor_device,
)

from tests.common import async_fire_time_changed


async def test_schedule_start_time(hass: HomeAssistant) -> None:
    """Test the frequency schedule start time."""

    now = dt_util.now()

    entry = mock_config_entry(hass)

    with patch_async_ble_device_from_address(), patch_melnor_device() as device_patch, patch_async_register_callback():
        device = device_patch.return_value

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        time_entity = hass.states.get("time.zone_1_schedule_start_time")

        assert time_entity is not None
        assert time_entity.state == device.zone1.frequency.start_time.isoformat()

        await hass.services.async_call(
            "time",
            "set_value",
            {"entity_id": "time.zone_1_schedule_start_time", "time": time(1, 0)},
            blocking=True,
        )

        async_fire_time_changed(hass, now + dt_util.dt.timedelta(seconds=10))
        await hass.async_block_till_done()

        time_entity = hass.states.get("time.zone_1_schedule_start_time")

        assert time_entity is not None
        assert time_entity.state == time(1, 0).isoformat()

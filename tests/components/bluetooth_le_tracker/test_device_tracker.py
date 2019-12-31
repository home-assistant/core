"""Test Bluetooth LE device tracker."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.components.bluetooth_le_tracker import device_tracker
from homeassistant.components.device_tracker.const import (
    CONF_SCAN_INTERVAL,
    CONF_TRACK_NEW,
    DOMAIN,
)
from homeassistant.components.device_tracker.legacy import YAML_DEVICES
from homeassistant.const import ATTR_NOW, CONF_PLATFORM, EVENT_TIME_CHANGED
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util, slugify

from tests.common import patch_yaml_files


async def test_preserve_new_tracked_device_name(hass):
    """Test preserving tracked device name across new seens."""

    address = "DE:AD:BE:EF:13:37"
    name = "Mock device name"
    entity_id = f"{DOMAIN}.{slugify(name)}"

    with patch(
        "homeassistant.components."
        "bluetooth_le_tracker.device_tracker.pygatt.GATTToolBackend"
    ) as mock_backend, patch.object(
        device_tracker, "MIN_SEEN_NEW", 3
    ), patch_yaml_files(  # Ignore possibly existing known_devices.yaml content
        {hass.config.path(YAML_DEVICES): ""}
    ), patch(  # Do not write known_devices.yaml
        "homeassistant.components.device_tracker.legacy.update_config"
    ):

        # Return with name when seen first time
        device = {"address": address, "name": name}
        mock_backend.return_value.scan.return_value = [device]

        config = {
            CONF_PLATFORM: "bluetooth_le_tracker",
            CONF_SCAN_INTERVAL: timedelta(minutes=1),
            CONF_TRACK_NEW: True,
        }
        result = await async_setup_component(hass, DOMAIN, {DOMAIN: config})
        assert result

        # Seen once here; return without name when seen subsequent times
        device["name"] = None

        # Tick until device seen enough times for to be registered for tracking
        for _ in range(device_tracker.MIN_SEEN_NEW - 1):
            hass.bus.async_fire(
                EVENT_TIME_CHANGED,
                {
                    ATTR_NOW: dt_util.utcnow()
                    + config[CONF_SCAN_INTERVAL]
                    + timedelta(seconds=1)
                },
            )
            await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.name == name

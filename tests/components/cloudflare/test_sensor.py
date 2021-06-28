"""Test the Cloudflare sensors."""
from datetime import datetime
from unittest.mock import patch

from homeassistant.components.cloudflare.const import DOMAIN
from homeassistant.const import ATTR_ICON, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import init_integration


async def test_sensors(hass, cfupdate):
    """Test integration sensors."""
    entry = await init_integration(hass, skip_setup=True)
    registry = er.async_get(hass)

    test_time = datetime(2021, 6, 27, 9, 10, 32, tzinfo=dt_util.UTC)
    with patch("homeassistant.components.cloudflare.sensor.utcnow", return_value=test_time):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.cloudflare_last_update")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:clock-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.state == "2021-06-27T15:37:00+00:00"

    entry = registry.async_get("sensor.cloudflare_last_update")
    assert entry
    assert entry.unique_id == "uuid_last_update"


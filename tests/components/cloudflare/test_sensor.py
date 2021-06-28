"""Test the Cloudflare sensors."""
from homeassistant.components.cloudflare.const import DOMAIN
from homeassistant.const import ATTR_ICON, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.helpers import entity_registry as er

from . import init_integration


async def test_sensors(hass, cfupdate):
    """Test integration sensors."""
    instance = cfupdate.return_value

    entry = await init_integration(hass)
    registry = er.async_get(hass)

    state = hass.states.get("sensor.cloudflare_last_update")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:clock-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.state == "2019-10-26T15:37:00+00:00"

    entry = registry.async_get("sensor.cloudflare_last_update")
    assert entry
    assert entry.unique_id == "uuid_last_update"


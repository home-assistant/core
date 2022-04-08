"""The tests for the uptime sensor platform."""
import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.freeze_time("2022-03-01 00:00:00+00:00")
async def test_uptime_sensor(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test Uptime sensor."""
    state = hass.states.get("sensor.uptime")
    assert state
    assert state.state == "2022-03-01T00:00:00+00:00"
    assert state.attributes["friendly_name"] == "Uptime"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("sensor.uptime")
    assert entry
    assert entry.unique_id == init_integration.entry_id

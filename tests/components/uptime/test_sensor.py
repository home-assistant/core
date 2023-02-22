"""The tests for the uptime sensor platform."""
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er


@pytest.mark.usefixtures("init_integration")
@pytest.mark.freeze_time("2022-03-01 00:00:00+00:00")
async def test_uptime_sensor(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Uptime sensor."""

    assert (state := hass.states.get("sensor.uptime"))
    assert state.state == "2022-03-01T00:00:00+00:00"
    assert state == snapshot

    assert (entity_entry := entity_registry.async_get(state.entity_id))
    assert entity_entry == snapshot

    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry == snapshot

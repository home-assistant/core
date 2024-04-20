"""Test binary sensor of NextDNS integration."""

from datetime import timedelta
from unittest.mock import patch

from nextdns import ApiError
from syrupy import SnapshotAssertion

from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from . import init_integration, mock_nextdns

from tests.common import async_fire_time_changed


async def test_binary_sensor(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test states of the binary sensors."""
    with patch("homeassistant.components.nextdns.PLATFORMS", [Platform.BINARY_SENSOR]):
        entry = await init_integration(hass)

    entity_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert (state := hass.states.get(entity_entry.entity_id))
        assert state == snapshot(name=f"{entity_entry.entity_id}-state")


async def test_availability(hass: HomeAssistant) -> None:
    """Ensure that we mark the entities unavailable correctly when service causes an error."""
    await init_integration(hass)

    state = hass.states.get("binary_sensor.fake_profile_device_connection_status")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == STATE_ON

    future = utcnow() + timedelta(minutes=10)
    with patch(
        "homeassistant.components.nextdns.NextDns.connection_status",
        side_effect=ApiError("API Error"),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("binary_sensor.fake_profile_device_connection_status")
    assert state
    assert state.state == STATE_UNAVAILABLE

    future = utcnow() + timedelta(minutes=20)
    with mock_nextdns():
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("binary_sensor.fake_profile_device_connection_status")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == STATE_ON

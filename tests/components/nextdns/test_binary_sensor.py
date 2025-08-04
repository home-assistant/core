"""Test binary sensor of NextDNS integration."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from nextdns import ApiError
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration, mock_nextdns

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_binary_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the binary sensors."""
    with patch("homeassistant.components.nextdns.PLATFORMS", [Platform.BINARY_SENSOR]):
        await init_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_availability(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure that we mark the entities unavailable correctly when service causes an error."""
    await init_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.fake_profile_device_connection_status")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == STATE_ON

    freezer.tick(timedelta(minutes=10))
    with patch(
        "homeassistant.components.nextdns.NextDns.connection_status",
        side_effect=ApiError("API Error"),
    ):
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("binary_sensor.fake_profile_device_connection_status")
    assert state
    assert state.state == STATE_UNAVAILABLE

    freezer.tick(timedelta(minutes=10))
    with mock_nextdns():
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("binary_sensor.fake_profile_device_connection_status")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == STATE_ON

"""Define tests for SimpliSafe setup."""

from unittest.mock import AsyncMock, Mock

from freezegun.api import FrozenDateTimeFactory
import pytest
from simplipy.errors import (
    EndpointUnavailableError,
    InvalidCredentialsError,
    RequestError,
    SimplipyError,
)
from simplipy.websocket import WebsocketEvent

from homeassistant.components.simplisafe import DOMAIN
from homeassistant.components.simplisafe.coordinator import DEFAULT_SCAN_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_base_station_migration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    api: Mock,
    config: dict[str, str],
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
) -> None:
    """Test that old integer-based device identifiers are migrated to strings."""
    old_identifiers = {(DOMAIN, 12345)}
    new_identifiers = {(DOMAIN, "12345")}

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers=old_identifiers,
        manufacturer="SimpliSafe",
        name="old",
    )

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert device_registry.async_get_device(identifiers=old_identifiers) is None
    assert device_registry.async_get_device(identifiers=new_identifiers) is not None


async def test_coordinator_update_triggers_reauth_on_invalid_credentials(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    system_v3,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that InvalidCredentialsError triggers a reauth flow."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    system_v3.async_update = AsyncMock(side_effect=InvalidCredentialsError("fail"))

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    flow = flows[0]
    assert flow.get("context", {}).get("source") == SOURCE_REAUTH
    assert flow.get("context", {}).get("entry_id") == config_entry.entry_id


@pytest.mark.parametrize(
    "exc",
    [RequestError, EndpointUnavailableError, SimplipyError],
)
async def test_coordinator_update_failure_keeps_entity_available(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    system_v3,
    freezer: FrozenDateTimeFactory,
    exc: type[SimplipyError],
) -> None:
    """Test that a single coordinator failure does not immediately mark entities unavailable."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("lock.front_door_lock").state != STATE_UNAVAILABLE

    system_v3.async_update = AsyncMock(side_effect=exc("fail"))

    # Trigger one coordinator failure: error_count goes from 0 to 1, below threshold.
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("lock.front_door_lock").state != STATE_UNAVAILABLE


async def test_websocket_event_updates_entity_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
) -> None:
    """Test that a push update from the websocket changes entity state."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Retrieve the event callback that was registered with the mock websocket.
    assert websocket.add_event_callback.called
    event_callback = websocket.add_event_callback.call_args[0][0]

    assert hass.states.get("lock.front_door_lock").state == "locked"

    # Fire an "unlock" websocket event for the test lock (system_id=12345, serial="987").
    # CID 9700 maps to EVENT_LOCK_UNLOCKED in the simplipy event mapping.
    event_callback(
        WebsocketEvent(
            event_cid=9700,
            info="Lock unlocked",
            system_id=12345,
            _raw_timestamp=0,
            _video=None,
            _vid=None,
            sensor_serial="987",
        )
    )
    await hass.async_block_till_done()

    assert hass.states.get("lock.front_door_lock").state == "unlocked"

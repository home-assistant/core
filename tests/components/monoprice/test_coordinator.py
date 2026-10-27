"""Tests for shared amplifier polling and per-zone results."""

import asyncio
from datetime import timedelta
from threading import Event
from unittest.mock import MagicMock, call

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from serialx import SerialException

from homeassistant.components.monoprice.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_CONFIG


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the shared 10 second timer fire once."""
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_enabled_zones_and_context_deduplication(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Only enabled zones are read, once each even with shared contexts."""
    assert client.zone_status.call_args_list == [call(11), call(12)]
    coordinator = entry.runtime_data.coordinator
    remove = coordinator.async_add_listener(lambda: None, context=11)
    client.zone_status.reset_mock()
    await _poll(hass, freezer)
    assert client.zone_status.call_args_list == [call(11), call(12)]
    remove()


@pytest.mark.parametrize(
    "failure", [None, SerialException("serial error"), TimeoutError("timeout")]
)
@pytest.mark.usefixtures("entry")
async def test_zone_failure_and_recovery(
    hass: HomeAssistant,
    client: MagicMock,
    freezer: FrozenDateTimeFactory,
    failure: SerialException | TimeoutError | None,
) -> None:
    """An unavailable zone does not hide a healthy sibling."""
    healthy = client.zone_status(12)
    client.zone_status.side_effect = [failure, healthy]
    await _poll(hass, freezer)
    assert hass.states.get("media_player.zone_11").state == "unavailable"
    assert hass.states.get("media_player.zone_12").state == "on"
    client.zone_status.side_effect = None
    await _poll(hass, freezer)
    assert hass.states.get("media_player.zone_11").state == "on"


@pytest.mark.usefixtures("entry")
async def test_all_zones_fail_and_recover(
    hass: HomeAssistant, client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Retry all enabled zones after a complete outage."""
    client.zone_status.side_effect = SerialException
    await _poll(hass, freezer)
    assert hass.states.get("media_player.zone_11").state == "unavailable"
    assert hass.states.get("media_player.zone_12").state == "unavailable"
    client.zone_status.side_effect = None
    await _poll(hass, freezer)
    assert hass.states.get("media_player.zone_11").state == "on"
    assert hass.states.get("media_player.zone_12").state == "on"


@pytest.mark.usefixtures("entry")
async def test_ten_second_poll_despite_command(
    hass: HomeAssistant,
    client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Targeted command read-back does not reset the other zones' timer."""
    client.zone_status.reset_mock()
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert client.zone_status.call_count == 0
    await hass.services.async_call(
        "media_player", "turn_off", {"entity_id": "media_player.zone_11"}, blocking=True
    )
    assert client.zone_status.call_args_list == [call(11)]
    assert hass.states.get("media_player.zone_11").state == "off"
    client.zone_status.reset_mock()
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert client.zone_status.call_args_list == [call(11), call(12)]


@pytest.mark.usefixtures("entry")
async def test_command_failed_readback(hass: HomeAssistant, client: MagicMock) -> None:
    """A failed read-back affects only the target zone."""
    client.zone_status.side_effect = SerialException
    await hass.services.async_call(
        "media_player", "turn_off", {"entity_id": "media_player.zone_11"}, blocking=True
    )
    assert hass.states.get("media_player.zone_11").state == "unavailable"
    assert hass.states.get("media_player.zone_12").state == "on"


async def test_command_failure_propagates(
    entry: MockConfigEntry, client: MagicMock
) -> None:
    """Do not report a failed command as successful or read a false result."""
    client.set_power.side_effect = SerialException
    client.zone_status.reset_mock()
    with pytest.raises(SerialException):
        await entry.runtime_data.coordinator.async_command(
            11, client.set_power, 11, False
        )
    client.zone_status.assert_not_called()


async def test_command_and_poll_are_serialized(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A poll cannot run between a command and its read-back."""
    started = asyncio.Event()
    release = Event()
    loop = asyncio.get_running_loop()

    def command() -> None:
        loop.call_soon_threadsafe(started.set)
        assert release.wait(5)
        client.set_power(11, False)

    coordinator = entry.runtime_data.coordinator
    client.zone_status.reset_mock()
    task = asyncio.create_task(coordinator.async_command(11, command))
    try:
        await asyncio.wait_for(started.wait(), 5)
        freezer.tick(timedelta(seconds=10))
        async_fire_time_changed(hass)
        for _ in range(10):
            await asyncio.sleep(0)
        client.zone_status.assert_not_called()
    finally:
        release.set()
    await task
    await hass.async_block_till_done(wait_background_tasks=True)
    assert client.zone_status.call_args_list == [call(11), call(11), call(12)]
    assert hass.states.get("media_player.zone_11").state == "off"


async def test_disable_reload_and_reenable(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Registry choices survive reload and newly enabled zones resume polling."""
    original_id = entity_registry.async_get("media_player.zone_11").id
    entity_registry.async_update_entity(
        "media_player.zone_11", disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    client.zone_status.reset_mock()
    await _poll(hass, freezer)
    assert client.zone_status.call_args_list == [call(12)]
    client.zone_status.reset_mock()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert client.zone_status.call_args_list == [call(12)]
    entity_registry.async_update_entity("media_player.zone_11", disabled_by=None)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("media_player.zone_11").state == "on"
    assert entity_registry.async_get("media_player.zone_11").id == original_id


async def test_unload_stops_polling(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Unloading removes the shared timer."""
    assert await hass.config_entries.async_unload(entry.entry_id)
    client.zone_status.reset_mock()
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    client.zone_status.assert_not_called()


async def test_no_enabled_zones(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An amplifier without listeners needs no startup or recurring reads."""
    for entity_id in ("media_player.zone_11", "media_player.zone_12"):
        entity_registry.async_update_entity(
            entity_id, disabled_by=er.RegistryEntryDisabler.USER
        )
    await hass.async_block_till_done()
    client.zone_status.reset_mock()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    client.zone_status.assert_not_called()


async def test_first_discovery_then_active_zones(
    hass: HomeAssistant,
    client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Probe optional zones once, then poll only discovered enabled players."""
    client.zone_status.side_effect = [client.zone_status(11)] * 6 + [None] * 12
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert (
        entity_registry.async_get("media_player.zone_21").disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )
    client.zone_status.side_effect = None
    client.zone_status.reset_mock()
    await _poll(hass, freezer)
    assert client.zone_status.call_args_list == [call(zone) for zone in range(11, 17)]


async def test_first_discovery_with_silent_optional_zones(
    hass: HomeAssistant, client: MagicMock, entity_registry: er.EntityRegistry
) -> None:
    """Actual serial timeouts from absent units must not prevent setup."""
    client.zone_status.side_effect = [client.zone_status(11)] * 6 + [
        TimeoutError()
    ] * 12
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("media_player.zone_11").state == "on"
    assert (
        entity_registry.async_get("media_player.zone_21").disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )
    assert len(hass.states.async_entity_ids("media_player")) == 6

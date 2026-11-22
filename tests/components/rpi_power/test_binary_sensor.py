"""Tests for rpi_power binary sensor."""

import asyncio
from datetime import timedelta
import logging
from types import TracebackType
from typing import Self
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    patch,
    snapshot_platform,
)
from rpi_bad_power import RpiBadPowerError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homeassistant import SERVICE_UPDATE_ENTITY
from homeassistant.components.rpi_power import binary_sensor
from homeassistant.components.rpi_power.binary_sensor import (
    DESCRIPTION_NORMALIZED,
    DESCRIPTION_UNDER_VOLTAGE,
)
from homeassistant.components.rpi_power.const import DOMAIN, ISSUE_UNDER_VOLTAGE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

ENTITY_ID = "binary_sensor.raspberry_pi_power_status"


async def _async_setup_component(hass: HomeAssistant, detected: bool) -> MagicMock:
    mocked_under_voltage = MagicMock(supports_push=False)
    type(mocked_under_voltage).get = MagicMock(return_value=detected)
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.rpi_power.new_under_voltage",
        return_value=mocked_under_voltage,
    ):
        await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()
    return mocked_under_voltage


async def test_new(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test new entry."""
    caplog.set_level(logging.DEBUG, logger=binary_sensor.__name__)
    await _async_setup_component(hass, False)
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_OFF
    assert not any(x.levelno == logging.WARNING for x in caplog.records)
    assert (
        binary_sensor.__name__,
        logging.DEBUG,
        DESCRIPTION_NORMALIZED,
    ) not in caplog.record_tuples
    assert not issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id=ISSUE_UNDER_VOLTAGE,
    )


async def test_new_detected(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test new entry with under voltage detected."""
    mocked_under_voltage = await _async_setup_component(hass, True)
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON
    assert (
        binary_sensor.__name__,
        logging.WARNING,
        DESCRIPTION_UNDER_VOLTAGE,
    ) in caplog.record_tuples

    # back to normal
    type(mocked_under_voltage).get = MagicMock(return_value=False)
    future = dt_util.utcnow() + timedelta(minutes=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_OFF
    assert (
        binary_sensor.__name__,
        logging.DEBUG,
        DESCRIPTION_NORMALIZED,
    ) in caplog.record_tuples

    issue = issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id="under_voltage_detected",
    )
    assert issue
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert issue.config_entry_id == entry.entry_id

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, "under_voltage_detected") is None


async def test_setup(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test states of binary sensor platform."""
    with patch(
        "homeassistant.components.rpi_power.new_under_voltage",
        return_value=MagicMock(supports_push=False, get=MagicMock(return_value=True)),
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, entry_id="12345")
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_read_error_unavailable_and_recovery(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test entity becomes unavailable on read error and recovers cleanly."""
    caplog.set_level(logging.INFO, logger=binary_sensor.__name__)
    mocked_under_voltage = await _async_setup_component(hass, False)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_OFF

    # First read failure: becomes unavailable and logs warning once
    type(mocked_under_voltage).get = MagicMock(
        side_effect=RpiBadPowerError("I/O error")
    )
    future = dt_util.utcnow() + timedelta(minutes=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNAVAILABLE
    error_warnings = [
        rec
        for rec in caplog.records
        if rec.name == binary_sensor.__name__
        and rec.levelno == logging.WARNING
        and "Error reading under-voltage status" in rec.message
    ]
    assert len(error_warnings) == 1

    # Repeated read failure: stays unavailable without logging duplicate warnings
    future += timedelta(minutes=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNAVAILABLE
    error_warnings = [
        rec
        for rec in caplog.records
        if rec.name == binary_sensor.__name__
        and rec.levelno == logging.WARNING
        and "Error reading under-voltage status" in rec.message
    ]
    assert len(error_warnings) == 1

    # Recovery with under-voltage active: becomes available, logs recovery, creates issue
    type(mocked_under_voltage).get = MagicMock(return_value=True)
    future += timedelta(minutes=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON
    assert (
        binary_sensor.__name__,
        logging.INFO,
        "Recovered reading under-voltage status",
    ) in caplog.record_tuples
    assert issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id=ISSUE_UNDER_VOLTAGE,
    )


class _FakeWatcher:
    """Deterministic async watcher for testing sysfs_notify push updates."""

    def __init__(self, events: asyncio.Queue[bool | BaseException]) -> None:
        self._events = events
        self.closed = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.closed = True

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> bool:
        item = await self._events.get()
        if isinstance(item, BaseException):
            raise item
        return item


async def test_push_notifications_and_unload(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test real-time sysfs_notify push updates and clean task cancellation."""
    caplog.set_level(logging.DEBUG, logger=binary_sensor.__name__)
    events: asyncio.Queue[bool | BaseException] = asyncio.Queue()
    watcher = _FakeWatcher(events)

    client = MagicMock(supports_push=True)
    client.get = MagicMock(return_value=False)
    client.async_watch = MagicMock(return_value=watcher)

    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.rpi_power.new_under_voltage",
        return_value=client,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_OFF

    # Duplicate initial emission does not log false normalization
    events.put_nowait(False)
    await asyncio.sleep(0)
    await hass.async_block_till_done()
    assert (
        binary_sensor.__name__,
        logging.DEBUG,
        DESCRIPTION_NORMALIZED,
    ) not in caplog.record_tuples

    # Push transition False -> True triggers warning and repair issue immediately
    events.put_nowait(True)
    await asyncio.sleep(0)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON
    assert (
        binary_sensor.__name__,
        logging.WARNING,
        DESCRIPTION_UNDER_VOLTAGE,
    ) in caplog.record_tuples
    assert issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id=ISSUE_UNDER_VOLTAGE,
    )

    # Manual update_entity while push watcher is active does not re-read or overwrite state
    client.get.reset_mock()
    await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})
    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    client.get.assert_not_called()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON

    # Push transition True -> False logs normalization
    events.put_nowait(False)
    await asyncio.sleep(0)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_OFF
    assert (
        binary_sensor.__name__,
        logging.DEBUG,
        DESCRIPTION_NORMALIZED,
    ) in caplog.record_tuples

    # Unloading cancels the watcher task and closes the watcher cleanly
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert watcher.closed is True


async def test_push_error_unavailable_and_retry(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test push watcher marks entity unavailable on OSError and retries cleanly."""
    caplog.set_level(logging.INFO, logger=binary_sensor.__name__)
    first_events: asyncio.Queue[bool | BaseException] = asyncio.Queue()
    second_events: asyncio.Queue[bool | BaseException] = asyncio.Queue()
    first_watcher = _FakeWatcher(first_events)
    second_watcher = _FakeWatcher(second_events)

    client = MagicMock(supports_push=True)
    client.get = MagicMock(return_value=False)
    client.async_watch = MagicMock(side_effect=[first_watcher, second_watcher])

    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.rpi_power.new_under_voltage",
            return_value=client,
        ),
        patch.object(binary_sensor, "PUSH_RETRY_INTERVAL", 0),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Simulate kernel/sysfs error during watch -> entity becomes unavailable
        first_events.put_nowait(RpiBadPowerError("I/O error"))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)
        assert state
        assert state.state == STATE_UNAVAILABLE

        # After retry, watcher emits True -> entity recovers and updates state
        second_events.put_nowait(True)
        await asyncio.sleep(0)
        await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)
        assert state
        assert state.state == STATE_ON
        assert (
            binary_sensor.__name__,
            logging.INFO,
            "Recovered reading under-voltage status",
        ) in caplog.record_tuples

        assert await hass.config_entries.async_unload(config_entry.entry_id)
        assert second_watcher.closed is True

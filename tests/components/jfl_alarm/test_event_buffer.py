"""The panel's event buffer (`0x48`), read through `coordinator.async_read_events` and the `read_event_buffer` service. Sprint 8.9.

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

The buffer is a log of things that already happened, and the records come back as service *data*
rather than being routed to any entity — this PR ships no `event` platform to route them to anyway,
so the tests here are only about the coordinator method and the service's own shape: the subject
naming, and the cursor a caller uses to resume.

Most of it is about paging. The panel returns eight records at a time, oldest first, forward only —
there is no request for "the newest twenty" — so the coordinator has to loop, and a simulator that
returned everything in one page would let a broken loop pass. `FakePanel.event_buffer` pages exactly
as the real one does.
"""

from __future__ import annotations

from dataclasses import replace

from pyjfl import UserRecord, ZoneRecord
import pytest

from homeassistant.components.jfl_alarm.const import CONF_READ_ONLY, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from tests.components.jfl_alarm.conftest import make_entry, wait_until
from tests.components.jfl_alarm.panel_sim import FakePanel

# (serial, Contact ID, subject, partition, BCD DD MM YY HH MM SS) — the shape of a real record.
_STAMP = [0x21, 0x03, 0x26, 0x15, 0x50, 0x23]


def _history(count: int, *, first_serial: int = 1) -> list:
    """A buffer of *count* ordinary arm/disarm records, oldest first."""
    return [
        (
            first_serial + index,
            "3401" if index % 2 else "1401",
            3,
            1,
            _STAMP,
        )
        for index in range(count)
    ]


async def _entry_for(hass: HomeAssistant, port: int, panel: FakePanel):
    entry = make_entry(
        port, serials=[panel.serial], subentry_data={CONF_READ_ONLY: True}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _bring_up(hass: HomeAssistant, entry, connect_panel, panel: FakePanel):
    coordinator = entry.runtime_data.coordinators[panel.serial]
    connection = await connect_panel(panel)
    await connection.introduce(hass)
    await connection.report_status(hass, coordinator)
    connection.serve_programming()
    return connection, coordinator


async def test_the_buffer_is_paged_until_it_runs_out(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """Twenty records is three pages of eight, and the loop has to ask for all three."""
    panel = FakePanel(serial="EVENTBUF01", events=_history(20))
    entry = await _entry_for(hass, port, panel)
    try:
        _, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        records = await coordinator.async_read_events()

        assert len(records) == 20, "a single page would have returned eight"
        assert [record.serial for record in records] == list(range(1, 21))
        assert records[0].contact_id == "1401"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_reading_resumes_from_a_cursor(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The only way to reach the newest records without re-reading everything."""
    panel = FakePanel(serial="EVENTCUR01", events=_history(20))
    entry = await _entry_for(hass, port, panel)
    try:
        _, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        records = await coordinator.async_read_events(since=15)

        assert [record.serial for record in records] == [16, 17, 18, 19, 20]
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_the_limit_is_a_hard_stop(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """1073 records is 135 round trips on a link that is also polling the status."""
    panel = FakePanel(serial="EVENTLIM01", events=_history(40))
    entry = await _entry_for(hass, port, panel)
    try:
        _, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        records = await coordinator.async_read_events(limit=10)

        assert len(records) == 10
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_an_empty_buffer_reads_as_nothing(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """A panel that has recorded nothing is a legitimate state, not a failure."""
    panel = FakePanel(serial="EVENTNIL01")
    entry = await _entry_for(hass, port, panel)
    try:
        _, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        assert await coordinator.async_read_events() == []
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_disconnect_mid_page_returns_what_was_already_read(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The panel hangs up half way through a 135-round-trip download.

    Partial history is worth having, and a traceback in a service call is not — the same treatment
    the wireless inventory gets. Modelled as two calls resuming from a cursor, the way a real caller
    would retry, rather than as one call spanning the disconnect: a future still in flight when the
    socket closes is cancelled by `_shutdown` (`asyncio.CancelledError`, not one of the three
    exceptions this branch catches), so the honest way to reach `_require_connection` actually
    raising `PanelNotConnectedError` is to have the panel already gone *before* the next page is
    asked for.
    """
    panel = FakePanel(serial="EVENTDISC1", events=_history(20))
    entry = await _entry_for(hass, port, panel)
    try:
        connection, coordinator = await _bring_up(hass, entry, connect_panel, panel)

        first_page = await coordinator.async_read_events(limit=8)
        assert len(first_page) == 8, (
            "sanity: a full page, exactly what the panel holds per page"
        )

        await connection.close()
        # `close()` returning is not the same moment the link notices: EOF is detected on the
        # listener's own read loop, asynchronously. The next page must not be asked for until the
        # link really has flipped, or the request goes out over a socket mid-teardown instead of
        # hitting `_require_connection`'s guard.
        await wait_until(hass, lambda: not coordinator.link.connected)

        records = await coordinator.async_read_events(since=8)
        assert records == [], "nothing raised for the panel that is no longer there"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_the_service_names_the_subject_and_returns_a_cursor(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The service response is what a person reads: a description, a name, and where to resume."""
    events = [(7, "3401", 3, 1, _STAMP), (8, "1130", 9, 1, _STAMP)]
    panel = FakePanel(serial="EVENTSVC01", events=events)
    entry = await _entry_for(hass, port, panel)
    try:
        _, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        coordinator.programming = replace(
            coordinator.programming,
            read_at=dt_util.utcnow(),
            users={
                3: UserRecord(
                    number=3, name="Bruno", has_code=True, attributes=bytes(8)
                )
            },
            zones={
                9: ZoneRecord(9, "Porta dos fundos", bytes.fromhex("10FFFF1101FFFF"))
            },
        )

        response = await hass.services.async_call(
            DOMAIN,
            "read_event_buffer",
            {"device_id": _panel_device_id(hass, entry.entry_id, panel.serial)},
            blocking=True,
            return_response=True,
        )

        assert response["count"] == 2
        assert response["next_serial"] == 8, "so the next call reads only what is new"
        armed, alarm = response["events"]
        assert armed["code"] == "3401"
        assert armed["description"]
        assert armed["subject_name"] == "Bruno"
        assert alarm["subject_kind"] == "zone"
        assert alarm["subject_name"] == "Porta dos fundos"
        assert alarm["timestamp"] == "21/03/26 15:50:23"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_an_origin_subject_is_never_looked_up_as_a_person(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """`000` and `099` are the app and the monitoring connection, not user 0 or user 99.

    A code whose subject kind **is** `user` (`3401`, armed) still must not be named here if the
    subject field itself is one of the two origins — that is a different guard from `is_fence`,
    which this record does not otherwise trigger (partition 1, not 99).
    """
    events = [(11, "3401", 0, 1, _STAMP)]
    panel = FakePanel(serial="EVENTORIG1", events=events)
    entry = await _entry_for(hass, port, panel)
    try:
        _, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        coordinator.programming = replace(
            coordinator.programming,
            read_at=dt_util.utcnow(),
            users={
                0: UserRecord(
                    number=0,
                    name="Should not appear",
                    has_code=False,
                    attributes=bytes(8),
                )
            },
        )

        response = await hass.services.async_call(
            DOMAIN,
            "read_event_buffer",
            {"device_id": _panel_device_id(hass, entry.entry_id, panel.serial)},
            blocking=True,
            return_response=True,
        )

        [armed] = response["events"]
        assert "subject_name" not in armed
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_subjectless_code_gets_no_name_at_all(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """`1301` (AC power lost) names neither a zone nor a user — `EventSubject.NONE`.

    Different from the origin guard above: here the code itself carries no subject to resolve, so
    `_subject_name` falls through both the `USER` and `ZONE` branches to its own empty default. The
    subject field is deliberately non-zero (`5`, not `0`) so this reaches that fallback rather than
    the earlier origin guard, which would return early on its own for the same empty result.
    """
    events = [(12, "1301", 5, 1, _STAMP)]
    panel = FakePanel(serial="EVENTNONE1", events=events)
    entry = await _entry_for(hass, port, panel)
    try:
        await _bring_up(hass, entry, connect_panel, panel)

        response = await hass.services.async_call(
            DOMAIN,
            "read_event_buffer",
            {"device_id": _panel_device_id(hass, entry.entry_id, panel.serial)},
            blocking=True,
            return_response=True,
        )

        [power_lost] = response["events"]
        assert power_lost["subject_kind"] == "none"
        assert "subject_name" not in power_lost
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_device_that_resolves_to_no_loaded_panel_fails_loudly(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The device exists, but the entry it belongs to has since been unloaded.

    Different from "device does not exist at all": here `dr.async_get(hass).async_get(device_id)`
    succeeds, so the failure has to come from the loop that walks the device's config entries and
    finds none of them still holding a coordinator for this serial.
    """
    panel = FakePanel(serial="EVENTUNLD1")
    entry = await _entry_for(hass, port, panel)
    device_id = _panel_device_id(hass, entry.entry_id, panel.serial)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "read_event_buffer",
            {"device_id": device_id},
            blocking=True,
            return_response=True,
        )


def _panel_device_id(hass: HomeAssistant, entry_id: str, serial: str) -> str:
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, serial), config_entry_id=entry_id
    )
    assert device is not None
    return device.id

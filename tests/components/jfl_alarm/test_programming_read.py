"""Reading the panel's programming through the coordinator, and what it changes in Home Assistant.

The frame-level parsing is covered by `pyjfl`'s own tests against real captured bytes; these are
about the round trip — thirty-odd requests paced over a live socket, correlated by their echoed
selector, and the names that land on the partition sub-device at the other end.
"""

from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import patch

from pyjfl.protocol.programming import REGIONS, plan_region
import pytest

from homeassistant.components.jfl_alarm import coordinator as coordinator_module
from homeassistant.components.jfl_alarm.const import CONF_READ_ONLY, DOMAIN
from homeassistant.components.jfl_alarm.device import get_sub_device
from homeassistant.core import HomeAssistant

from .conftest import make_entry
from .panel_sim import FakePanel

SHORT_TIMEOUT = patch("pyjfl.transport.COMMAND_TIMEOUT", 0.05)
"""Shortens the per-block timeout so the give-up path is testable in a second, not a minute."""

NAMED_PANEL = {
    # **Nine characters, because that is the field width.** A longer name is truncated by the panel
    # itself, not by us, and a test that used twelve would be testing a panel that cannot exist.
    "zone_names": {1: "P Frente", 2: "Cozinha", 9: "Garagem"},
    "partition_names": {1: "Interno", 2: "Externo"},
    "pgm_names": {1: "Portao", 2: "Home Assi"},
    "wireless_devices": {0xB205AF2A: 9},
    "zones": {1: 0x8, 2: 0x8, 9: 0x8},
}


async def _bring_up(hass: HomeAssistant, entry, connect_panel, panel: FakePanel):
    """Connect *panel*, absorb one status frame, and let it answer programming reads."""
    coordinator = entry.runtime_data.coordinators[panel.serial]
    connection = await connect_panel(panel)
    await connection.introduce(hass)
    await connection.report_status(hass, coordinator)
    connection.serve_programming()
    return connection, coordinator


async def _entry_for(
    hass: HomeAssistant, port: int, panel: FakePanel, **subentry: object
):
    entry = make_entry(
        port, serials=[panel.serial], subentry_data={CONF_READ_ONLY: True, **subentry}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


# --- 6.2: the round trip ------------------------------------------------------------------------


async def test_a_full_read_assembles_every_region(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """Thirty-odd requests, paced, correlated by the selector each reply echoes."""
    panel = FakePanel(serial="PROGREAD01", **NAMED_PANEL)
    entry = await _entry_for(hass, port, panel)
    try:
        _, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        programming = await coordinator.async_read_programming()

        assert programming.incomplete == (), "every region came back"
        assert programming.read is True
        assert programming.zone_name(1) == "P Frente"
        assert programming.zone_name(2) == "Cozinha"
        assert programming.partition_name(1) == "Interno"
        assert programming.pgms[2].name == "Home Assi"
        assert programming.checksum == panel.checksum
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_read_runs_in_read_only_mode(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """`0x44` asks a question. Read-only means the integration never *writes*, not never speaks.

    The same reasoning that keeps the status poll running — and it is load-bearing here, because a
    fresh installation is read-only and the zone names are the first thing anybody wants.
    """
    panel = FakePanel(serial="READONLY01", **NAMED_PANEL)
    entry = await _entry_for(hass, port, panel, **{CONF_READ_ONLY: True})
    try:
        _, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        assert coordinator.read_only is True

        programming = await coordinator.async_read_programming()
        assert programming.zone_name(1) == "P Frente"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_panel_that_never_answers_gives_up_and_says_which_regions(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """A region that fails is named, and the rest is kept.

    Thirty-one zone names are worth having when zone 32's request went astray — and a panel that
    does not implement `0x44` at all should degrade to "no names", not to an exception.
    """
    panel = FakePanel(serial="SILENT0001")
    entry = await _entry_for(hass, port, panel)
    try:
        # Deliberately *not* calling `serve_programming()`: nothing answers.
        coordinator = entry.runtime_data.coordinators[panel.serial]
        connection = await connect_panel(panel)
        await connection.introduce(hass)
        await connection.report_status(hass, coordinator)

        with SHORT_TIMEOUT:
            programming = await coordinator.async_read_programming()

        assert set(programming.incomplete) == {
            "partition_names",
            "pgms",
            "users",
            "zones",
            "wireless",
            "holidays",
            "timers",
            "zone_options",
        }
        assert programming.zones == {}
        assert programming.zone_name(1) == "", "no name, and no exception"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


# --- 6.4: names on the devices ------------------------------------------------------------------


async def test_a_partition_takes_the_panels_own_name(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The headline of the sprint: `Partition 1 Interno` instead of `Partition 1`.

    **The name has to come from a translation key, not an f-string.** Composing it literally is
    what put an English word on a Portuguese device page in the zone-naming case this shares its
    machinery with. `DeviceEntry` resolves the key into `name` and does not keep it, so the half of
    this that an English test run cannot see is asserted in `tests/test_translations.py`.
    """
    panel = FakePanel(serial="NAMES00001", **NAMED_PANEL)
    entry = await _entry_for(hass, port, panel)
    try:
        _, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        await coordinator.async_read_programming()

        partition = get_sub_device(
            hass, entry.entry_id, (DOMAIN, f"{panel.serial}-partition1")
        )
        assert partition.name == "Interno"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


# --- 6.5: reads only, and no codes ---------------------------------------------------------------


async def test_nothing_in_this_sprint_can_write(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """`0x45`, the programming *write*, exists in no code path this integration can reach."""
    source = (
        __import__("pathlib")
        .Path(coordinator_module.__file__)
        .read_text(encoding="utf-8")
    )
    assert "WRITE_PROGRAMMING" not in source
    assert "build_programming_write" not in source


@pytest.mark.parametrize(
    "region", ["zones", "partition_names", "users", "pgms", "wireless"]
)
def test_every_region_is_planned_from_the_documented_map(region: str) -> None:
    """A region whose plan does not start at its base would read somebody else's records."""
    requests = plan_region(region)
    assert requests[0].address == REGIONS[region][0]


# --- the automatic read loop ----------------------------------------------------------------------


NO_DELAY = patch.object(coordinator_module, "PROGRAMMING_READ_FIRST_DELAY", 0)
"""The loop waits before its first read so the panel has introduced itself. The tests below have
already brought a panel up, so there is nothing left to wait for."""


async def _run_loop_once(coordinator, hass: HomeAssistant) -> None:
    """Drive `_read_programming_forever` through exactly one tick, then stop it.

    The loop is infinite, and every branch of it ends by sleeping for `_programming_sleep()`. So
    that is where the tick is cut short: whatever it decided has already happened by then.
    """
    # The coordinator runs this loop itself, as a background task. Two of them would drive two
    # programming reads down the same socket at once, so the real one is stopped first.
    if coordinator._programming_task is not None:
        coordinator._programming_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await coordinator._programming_task
        coordinator._programming_task = None

    with (
        NO_DELAY,
        patch.object(
            coordinator, "_programming_sleep", side_effect=asyncio.CancelledError
        ),
        contextlib.suppress(asyncio.CancelledError),
    ):
        await coordinator._read_programming_forever()
    await hass.async_block_till_done()


async def test_the_loop_reads_a_panel_that_has_just_connected(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The first read is automatic, so a fresh panel shows its own names without anyone asking."""
    panel = FakePanel(serial="AUTOREAD01", **NAMED_PANEL)
    entry = await _entry_for(hass, port, panel)
    try:
        _, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        assert coordinator.programming.read is False

        await _run_loop_once(coordinator, hass)

        assert coordinator.programming.read is True
        assert coordinator.programming.partition_name(1) == "Interno"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_the_loop_asks_a_silent_panel_once_and_then_leaves_it_alone(
    hass: HomeAssistant,
    port: int,
    connect_panel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A panel that does not implement `0x44` is flagged, and never asked again automatically."""
    panel = FakePanel(serial="NOPROG0001")
    entry = await _entry_for(hass, port, panel)
    try:
        connection = await connect_panel(panel)
        await connection.introduce(hass)
        coordinator = entry.runtime_data.coordinators[panel.serial]
        await connection.report_status(hass, coordinator)
        # Deliberately no `serve_programming()`: nothing answers.

        with SHORT_TIMEOUT:
            await _run_loop_once(coordinator, hass)
        assert coordinator._programming_unreadable is True
        assert "did not answer the programming read" in caplog.text
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_the_loop_skips_a_re_read_while_the_checksum_is_unchanged(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """`KP` changes only when the programming does, so an unchanged panel costs one comparison."""
    panel = FakePanel(serial="SAMEKP0001", **NAMED_PANEL)
    entry = await _entry_for(hass, port, panel)
    try:
        _, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        await coordinator.async_read_programming()
        read_at = coordinator.programming.read_at

        with patch.object(coordinator.link, "async_read_programming") as read_again:
            await _run_loop_once(coordinator, hass)
        read_again.assert_not_called()
        assert coordinator.programming.read_at == read_at
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

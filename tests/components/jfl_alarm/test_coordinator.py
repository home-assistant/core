"""The coordinator, the entry lifecycle and the repair issues."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pyjfl import Cmd, FrameReader, build_frame
import pytest

from homeassistant.components.jfl_alarm import async_remove_config_entry_device
from homeassistant.components.jfl_alarm.const import (
    CONF_SERIAL,
    DOMAIN,
    SUBENTRY_TYPE_PANEL,
)
from homeassistant.components.jfl_alarm.coordinator import JflPanelCoordinator
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import LOOPBACK, make_entry, wait_until
from .panel_sim import FakePanel

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_the_snapshot_is_never_none(hass: HomeAssistant, setup_entry) -> None:
    """Entities are created before any panel has dialled in, so `data` must already exist."""
    [coordinator] = list(setup_entry.runtime_data.coordinators.values())
    assert coordinator.data is not None
    assert coordinator.data.connection is None
    assert coordinator.data.available is False
    # And the permissive model fallback stands in, rather than raising.
    assert coordinator.data.spec.partitions > 0
    assert coordinator.data.partitions == ()


async def test_a_subentry_of_a_foreign_type_is_skipped(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """Only a `panel` subentry becomes a coordinator; anything else is ignored, not rejected.

    Nothing in this integration creates a second subentry type today, but the loop guards against
    one anyway — forward compatibility, or a subentry some other code path added by mistake — and
    that guard is worth proving does not also skip the genuine panel sitting right next to it.
    """
    panel = FakePanel(serial="MIXEDSUB01")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="JFL Alarm (mixed subentries)",
        data={CONF_HOST: LOOPBACK, CONF_PORT: port},
        unique_id=str(port),
        subentries_data=[
            ConfigSubentryData(
                data={CONF_SERIAL: panel.serial, "read_only": True},
                subentry_type=SUBENTRY_TYPE_PANEL,
                title="Active 32 Duo",
                unique_id=panel.serial,
            ),
            ConfigSubentryData(
                data={},
                subentry_type="something_else",
                title="Not a panel",
                unique_id="not-a-panel",
            ),
        ],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    try:
        assert set(entry.runtime_data.coordinators) == {panel.serial}
        connection = await connect_panel(panel)
        await connection.introduce(hass)
        assert entry.runtime_data.server.link(panel.serial).connected
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_setup_does_not_fail_when_no_panel_is_there(
    hass: HomeAssistant, setup_entry
) -> None:
    """`async_config_entry_first_refresh` is deliberately never called.

    A panel typically dials in ten to sixty seconds after Home Assistant starts. A first refresh
    would turn "the panel is still booting" into "the integration failed to set up".
    """
    assert setup_entry.state is ConfigEntryState.LOADED


async def test_an_undecodable_command_is_counted_not_dropped(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """An unknown command is how the next undocumented one gets found."""
    coordinator = setup_entry.runtime_data.coordinators[panel.serial]
    connection = await connect_panel(panel)
    await connection.introduce(hass)

    await connection.send(build_frame(0x42, 0x7E, b"\x01\x02\x03"))
    await wait_until(hass, lambda: coordinator.data.unknown_packets == 1)


async def test_the_poll_loop_asks_on_its_interval(
    # `freezer` is requested **before** anything that schedules a timer. Starting freezegun after
    # a timer exists moves the clock underneath it, and the timer fires immediately.
    freezer: FrozenDateTimeFactory,
    hass: HomeAssistant,
    port: int,
    connect_panel,
) -> None:
    """The panel never volunteers its status, so something has to ask on a schedule."""
    entry = make_entry(port)
    entry.add_to_hass(hass)
    with patch("homeassistant.components.jfl_alarm.DEFAULT_STATUS_INTERVAL", 5):
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    try:
        panel = FakePanel()
        connection = await connect_panel(panel)
        await connection.introduce(hass)

        freezer.tick(timedelta(seconds=6))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        reply = await connection.read_reply()
        assert FrameReader().feed(reply)[0].cmd == Cmd.STATUS
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_availability_is_logged_once_per_transition(
    hass: HomeAssistant,
    setup_entry,
    connect_panel,
    panel: FakePanel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A panel that redials every ninety seconds must not fill the log with a pair of lines."""
    coordinator = setup_entry.runtime_data.coordinators[panel.serial]

    first = await connect_panel(panel)
    await first.introduce(hass)
    await first.close()
    await wait_until(hass, lambda: not coordinator.data.available)

    # Both directions log at info — the quality-scale rule `log-when-unavailable` asks for that
    # level unconditionally, on both the disappearance and the return.
    infos = [record for record in caplog.records if record.levelname == "INFO"]
    assert sum("stopped reporting" in record.message for record in infos) == 1

    caplog.clear()
    second = await connect_panel(panel)
    await second.introduce(hass)
    await wait_until(hass, lambda: coordinator.data.available)

    # Recovery is one line at info, and it is not repeated.
    assert sum("is reporting again" in record.message for record in caplog.records) == 1


async def test_reloading_the_entry_leaves_no_listener_behind(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """A reload that leaked its listener would make every later reload fail on a busy port."""
    connection = await connect_panel(panel)
    await connection.introduce(hass)

    assert await hass.config_entries.async_reload(setup_entry.entry_id)
    await hass.async_block_till_done()
    assert setup_entry.state is ConfigEntryState.LOADED

    # The panel redials after a reload, exactly as it does after a restart.
    again = await connect_panel(panel)
    await again.introduce(hass)
    assert setup_entry.runtime_data.server.link(panel.serial).connected


async def test_the_device_of_a_removed_panel_can_be_deleted(
    hass: HomeAssistant,
    setup_entry,
    connect_panel,
    panel: FakePanel,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A replaced panel leaves a device that will never update again."""
    connection = await connect_panel(panel)
    await connection.introduce(hass)

    live = device_registry.async_get_device_by_identifier(
        (DOMAIN, panel.serial), config_entry_id=setup_entry.entry_id
    )
    assert live is not None
    assert not await async_remove_config_entry_device(hass, setup_entry, live)

    stale = device_registry.async_get_or_create(
        config_entry_id=setup_entry.entry_id, identifiers={(DOMAIN, "GONEPANEL1")}
    )
    assert await async_remove_config_entry_device(hass, setup_entry, stale)


async def test_a_partition_number_outside_the_model_returns_none(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """`partition()` is 1-based and bounded by the model, not by whatever number is asked for.

    Called directly on the snapshot rather than through an entity: every partition entity this
    integration creates is already valid for its model, so there is no `alarm_control_panel` that
    would ever ask for partition 0 or partition 99. The bound check still has to hold for a caller
    that does — `entity.py`'s own `snapshot` property is what every platform actually calls this
    through.
    """
    coordinator = setup_entry.runtime_data.coordinators[panel.serial]
    connection = await connect_panel(panel)
    await connection.introduce(hass)
    await connection.report_status(hass, coordinator)

    assert coordinator.data.partition(0) is None
    assert coordinator.data.partition(99) is None
    assert coordinator.data.partition(1) is not None, (
        "sanity: a real partition still resolves"
    )


async def test_setup_panel_notices_a_link_already_connected(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """`async_setup_panel` checks `link.connected` for a real race, not a hypothetical one.

    `async_setup_entry` starts the listener, then calls `async_setup_panel` once per subentry in a
    loop — so with more than one panel configured, a socket accepted while an earlier subentry's
    setup is still running is already bound to its `JflPanelLink` by the time a later subentry's
    coordinator is built. Reproduced here with a second, throwaway coordinator on the same already
    -connected link, rather than by racing two real sockets against subentry ordering — and shut
    down again immediately, so it leaves nothing behind for `setup_entry`'s own teardown to trip on.
    """
    live = setup_entry.runtime_data.coordinators[panel.serial]
    connection = await connect_panel(panel)
    await connection.introduce(hass)
    assert live.link.connected

    second = JflPanelCoordinator(hass, setup_entry, live.subentry, live.link)
    try:
        await second.async_setup_panel()
        await hass.async_block_till_done()
        assert second.data.available is True, (
            "the link was already connected, so setup itself must notice"
        )
    finally:
        await second.async_shutdown_panel()

"""PGM outputs, zone bypass and the service layer.

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

Sprint 4. Two things here are worth more than the coverage they add.

**The bypass bitmap is a read-modify-write, and the test that matters is the one where another zone
is already inhibited.** `0x52` replaces the whole map, so bypassing zone 10 while zone 9 is bypassed
must send *both* — a version that sent only zone 10 would pass a naive test and silently un-inhibit
zone 9 on a real panel.

**The fence PGM is the one entity in the integration that can do real damage.** A PGM programmed
with function 18 is the fence's power supply, so switching it off turns the fence off without the
fence entity knowing. It is tested for *where it ends up* — the fence's own device, in the
configuration section — not merely for being labelled. ADR-0017.

**Every PGM test has to get past `pgm_functions_known` first.** The switches are not created until
the panel has said what its outputs do, so `_bring_up` announces a programming snapshot; the tests
that assert on command frames cannot serve a real read, because that read and their own assertions
would be reading the same socket.
"""

from __future__ import annotations

import asyncio

import pytest
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pyjfl import Cmd, FrameReader, bitmap_to_flags

from homeassistant.components.jfl_alarm.const import CONF_FENCE_PGM, CONF_READ_ONLY, DOMAIN
from homeassistant.components.jfl_alarm.device import get_sub_device
from tests.components.jfl_alarm.conftest import announce_programming, make_entry
from tests.components.jfl_alarm.panel_sim import FakePanel


async def _bring_up(
    hass: HomeAssistant,
    entry,
    connect_panel,
    panel: FakePanel,
    pgms: dict[int, int] | None = None,
):
    """Connect *panel*, absorb one status frame, and settle its PGM functions.

    *pgms* maps PGM number to function byte, and defaults to none of them being known — which is a
    panel whose PGM region did not come back, and produces four ordinary switches. That is what most
    of these tests want; the fence test names a function on purpose.
    """
    coordinator = entry.runtime_data.coordinators[panel.serial]
    connection = await connect_panel(panel)
    await connection.introduce(hass)
    await connection.report_status(hass, coordinator)
    announce_programming(coordinator, pgms)
    await hass.async_block_till_done()
    return connection, coordinator


async def _writable_entry(hass: HomeAssistant, port: int, panel: FakePanel, **subentry: object):
    """Set up an entry for *panel* with `read_only` off."""
    entry = make_entry(
        port, serials=[panel.serial], subentry_data={CONF_READ_ONLY: False, **subentry}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _next_command(connection, timeout: float = 2.0):
    """Return the next frame written that is not one of the post-command status re-reads."""
    reader = FrameReader()
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        for frame in reader.feed(await connection.read_reply(timeout=timeout)):
            if frame.cmd != Cmd.STATUS:
                return frame
    raise AssertionError("no command frame arrived")


def _panel_device_id(hass: HomeAssistant, entry_id: str, serial: str) -> str:
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, serial), config_entry_id=entry_id
    )
    assert device is not None
    return device.id


# --- PGM outputs ------------------------------------------------------------------------------


async def test_a_pgm_switch_exists_per_output_the_model_has(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """An Active 32 Duo has four. Not sixteen, and not zero."""
    panel = FakePanel(serial="PGMCOUNT01")
    entry = await _writable_entry(hass, port, panel)
    try:
        await _bring_up(hass, entry, connect_panel, panel)
        assert hass.states.get("switch.active_32_duo_pgm_1") is not None
        assert hass.states.get("switch.active_32_duo_pgm_4") is not None
        assert hass.states.get("switch.active_32_duo_pgm_5") is None
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("service", "expected_cmd"), [("turn_on", Cmd.PGM_ON), ("turn_off", Cmd.PGM_OFF)]
)
async def test_a_pgm_switch_sends_the_captured_frame(
    hass: HomeAssistant, port: int, connect_panel, service: str, expected_cmd: Cmd
) -> None:
    """Captured from ActiveNet: `7B 06 45 50 02 6A` on, `7B 06 49 51 02 67` off, for PGM 2."""
    panel = FakePanel(serial="PGMCMD0001")
    entry = await _writable_entry(hass, port, panel)
    try:
        connection, _ = await _bring_up(hass, entry, connect_panel, panel)
        await hass.services.async_call(
            "switch", service, {"entity_id": "switch.active_32_duo_pgm_2"}, blocking=True
        )
        frame = await _next_command(connection)
        assert frame.cmd == expected_cmd
        assert frame.raw[4] == 0x02
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_pgm_state_comes_from_the_right_byte(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """PGM 1-8 at offset 13 and 9-16 at **117** — the old integration reads 116, a `P-INIB` byte."""
    panel = FakePanel(
        serial="PGMSTATE01",
        model_byte=0xA4,  # Active 100 Bus: sixteen PGMs
        pgm=0b0000_0010,  # PGM 2 on. LSB is PGM 1.
        pgm_high=0b0000_0001,  # PGM 9 on.
    )
    entry = await _writable_entry(hass, port, panel)
    try:
        await _bring_up(hass, entry, connect_panel, panel)
        assert hass.states.get("switch.active_32_duo_pgm_1").state == "off"
        assert hass.states.get("switch.active_32_duo_pgm_2").state == "on"
        assert hass.states.get("switch.active_32_duo_pgm_9").state == "on"
        assert hass.states.get("switch.active_32_duo_pgm_10").state == "off"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_pgm_the_panel_will_not_operate_refuses_before_sending(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """`P-PGM` is clear for a PGM that is not programmed, or whose function is not user-operable.

    Only functions 12 and 13 are, and the panel answers anything else with silence on this command
    path — so the check has to happen here, where the message can name addresses 821-824.
    """
    panel = FakePanel(serial="PGMDENY001", pgm_permissions=0b0000_0001)  # only PGM 1
    entry = await _writable_entry(hass, port, panel)
    try:
        connection, _ = await _bring_up(hass, entry, connect_panel, panel)
        assert hass.states.get("switch.active_32_duo_pgm_2").attributes["can_operate"] is False

        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                "switch", "turn_on", {"entity_id": "switch.active_32_duo_pgm_2"}, blocking=True
            )
        with pytest.raises(TimeoutError):
            await connection.read_reply(timeout=0.3)
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_the_energisers_pgm_gets_no_switch_at_all(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The output on function 18 **triggers** the fence, so no entity is created for it.

    It is a two-second pulse on the energiser's *LIGA* terminal, not the fence's supply: `P-PGM`
    would refuse the command, its state reads `off` for ever between pulses, and the only thing it
    could do is flip the energiser behind the fence entity's back. The fence's own switch is how it
    is operated, and the diagnostics download is where the output can still be seen. ADR-0017.
    """
    panel = FakePanel(serial="FENCEPGM01")
    entry = await _writable_entry(hass, port, panel, **{CONF_FENCE_PGM: 3})
    try:
        await _bring_up(hass, entry, connect_panel, panel)

        entities = er.async_get(hass)
        assert entities.async_get_entity_id("switch", DOMAIN, f"{panel.serial}-pgm3") is None

        # And the others are ordinary switches, on the panel.
        ordinary = entities.async_get(
            entities.async_get_entity_id("switch", DOMAIN, f"{panel.serial}-pgm2")
        )
        assert ordinary.disabled_by is None
        assert ordinary.entity_category is None
        assert ordinary.device_id == _panel_device_id(hass, entry.entry_id, panel.serial)
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_an_older_installations_fence_pgm_switch_is_deleted(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """Not creating an entity is not enough — the row an earlier version left has to be removed.

    Home Assistant keeps a registry row whose entity is no longer provided and shows it greyed out,
    reading *no longer being provided*. That is worse than the switch it replaced, so the row is
    deleted once, the first time this platform runs against a panel that has a fence.
    """
    panel = FakePanel(serial="FENCELEGCY")
    entry = make_entry(port, serials=[panel.serial], subentry_data={CONF_READ_ONLY: False})
    entry.add_to_hass(hass)
    entities = er.async_get(hass)
    legacy = entities.async_get_or_create(
        "switch",
        DOMAIN,
        f"{panel.serial}-pgm3",
        config_entry=entry,
        config_subentry_id=next(iter(entry.subentries)),
    )
    assert entities.async_get(legacy.entity_id) is not None

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    try:
        await _bring_up(hass, entry, connect_panel, panel, pgms={3: 18})
        assert entities.async_get(legacy.entity_id) is None, "the stale row is gone, not greyed out"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_panel_with_no_fence_still_marks_an_energiser_output(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The one case that keeps ADR-0007's treatment: a fence PGM on a panel reporting no fence.

    There is no fence entity to operate and no fence device to give the output context, so the
    switch is the only trace of the contradiction — created, disabled, and marked as configuration.
    """
    panel = FakePanel(serial="NOFENCEPGM", model_byte=0xA0, fence=0x00)
    entry = await _writable_entry(hass, port, panel)
    try:
        await _bring_up(hass, entry, connect_panel, panel, pgms={2: 18})

        entities = er.async_get(hass)
        marked = entities.async_get(
            entities.async_get_entity_id("switch", DOMAIN, f"{panel.serial}-pgm2")
        )
        assert marked is not None, "created: it is the only sign that the programming disagrees"
        assert marked.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert marked.entity_category is EntityCategory.CONFIG
        assert marked.device_id == _panel_device_id(hass, entry.entry_id, panel.serial)
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_pgm_the_panel_does_not_use_is_created_disabled(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """Function 0 is *desabilitada*: the output does nothing, so its switch is not a control.

    It is still **created**, because an installer has to be able to see that the output exists — it
    is one click from visible, in the device's configuration section.
    """
    panel = FakePanel(serial="PGMUNUSED1")
    entry = await _writable_entry(hass, port, panel)
    try:
        await _bring_up(hass, entry, connect_panel, panel, pgms={1: 12, 2: 0})

        entities = er.async_get(hass)
        unused = entities.async_get(
            entities.async_get_entity_id("switch", DOMAIN, f"{panel.serial}-pgm2")
        )
        assert unused is not None, "created, not hidden"
        assert unused.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert unused.entity_category is EntityCategory.CONFIG
        assert hass.states.get(unused.entity_id) is None, "disabled entities have no state"

        in_use = entities.async_get(
            entities.async_get_entity_id("switch", DOMAIN, f"{panel.serial}-pgm1")
        )
        assert in_use.disabled_by is None
        assert in_use.entity_category is None
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_an_older_installations_unused_pgm_is_disabled_once_and_only_once(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """A row an earlier version created enabled learns it is unused — and then never again.

    `entity_registry_enabled_default` is honoured only when a row is *created*, so an upgrade would
    otherwise leave the switch for an unused output sitting in *Controls* for ever. Saying it once
    fixes that; saying it twice would undo a user who deliberately enabled the entity afterwards.
    """
    panel = FakePanel(serial="PGMLEGACY1")
    entities = er.async_get(hass)
    entry = make_entry(port, serials=[panel.serial], subentry_data={CONF_READ_ONLY: False})
    entry.add_to_hass(hass)
    subentry_id = next(iter(entry.subentries))
    # Registry rows exactly as Sprint 4 would have left them: enabled, no placement marker. PGM 1 is
    # an **ordinary** output and is here on purpose: settling has to walk over a row it must leave
    # alone without tripping, which is the shape of the bug the lab found on 2026-08-10.
    ordinary = entities.async_get_or_create(
        "switch", DOMAIN, f"{panel.serial}-pgm1", config_entry=entry, config_subentry_id=subentry_id
    )
    legacy = entities.async_get_or_create(
        "switch", DOMAIN, f"{panel.serial}-pgm2", config_entry=entry, config_subentry_id=subentry_id
    )
    assert legacy.disabled_by is None

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    try:
        await _bring_up(hass, entry, connect_panel, panel, pgms={1: 12, 2: 0})
        settled = entities.async_get(legacy.entity_id)
        assert settled.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert entities.async_get(ordinary.entity_id).disabled_by is None, "left as it was"

        # The user disagrees and switches it back on. A later run must leave that alone.
        entities.async_update_entity(legacy.entity_id, disabled_by=None)
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        await _bring_up(hass, entry, connect_panel, panel, pgms={2: 0})
        assert entities.async_get(legacy.entity_id).disabled_by is None
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


# --- zone bypass ------------------------------------------------------------------------------


async def test_bypass_switches_exist_only_for_zones_the_panel_permits(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """`P-INIB` is a programming choice, so it can decide whether the entity exists at all."""
    # LSB-first: byte 1 bit 0 is zone 1. Zones 1 and 2 may be bypassed; zone 9 may not.
    permits = bytes([0b0000_0011]) + bytes(12)
    panel = FakePanel(serial="BYPASSSEL1", bypassable=permits, zones={1: 0x8, 2: 0x8, 9: 0x8})
    entry = await _writable_entry(hass, port, panel)
    try:
        await _bring_up(hass, entry, connect_panel, panel)
        assert hass.states.get("switch.zone_1_bypass") is not None
        assert hass.states.get("switch.zone_2_bypass") is not None
        assert hass.states.get("switch.zone_9_bypass") is None
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_bypassing_a_zone_keeps_every_other_bypass(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The test that matters. `0x52` replaces the **whole** bitmap.

    Zone 9 is already inhibited when zone 1 is bypassed, so the frame must carry both. A version
    that sent only the zone being changed would pass every other test in this file and silently
    un-inhibit zone 9 on a real panel.
    """
    panel = FakePanel(
        serial="BYPASSRMW1",
        bypassable=bytes([0xFF]) + bytes([0xFF]) + bytes(11),
        zones={1: 0x8, 9: 0x1},  # zone 9 already manually bypassed
    )
    entry = await _writable_entry(hass, port, panel)
    try:
        connection, _ = await _bring_up(hass, entry, connect_panel, panel)
        assert hass.states.get("switch.zone_9_bypass").state == "on"

        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.zone_1_bypass"},
            blocking=True,
        )
        frame = await _next_command(connection)
        assert frame.cmd == Cmd.BYPASS
        # The command's bitmap is **MSB-first**, the opposite of `P-INIB`. Decoding it that way is
        # the only way this assertion means anything.
        assert bitmap_to_flags(frame.raw[4:17], lsb_first=False) == frozenset({1, 9})
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_un_bypassing_removes_only_that_zone(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The other half of the read-modify-write."""
    panel = FakePanel(
        serial="BYPASSOFF1",
        bypassable=bytes([0xFF, 0xFF]) + bytes(11),
        zones={1: 0x1, 9: 0x1},
    )
    entry = await _writable_entry(hass, port, panel)
    try:
        connection, _ = await _bring_up(hass, entry, connect_panel, panel)
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": "switch.zone_1_bypass"},
            blocking=True,
        )
        frame = await _next_command(connection)
        assert bitmap_to_flags(frame.raw[4:17], lsb_first=False) == frozenset({9})
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


# --- services ---------------------------------------------------------------------------------


async def test_the_services_are_registered_without_any_entry(hass: HomeAssistant) -> None:
    """Registered in `async_setup`, so an automation validates while the entry is unloaded."""
    from homeassistant.components.jfl_alarm import async_setup

    assert await async_setup(hass, {})
    for service in ("sync_time", "refresh_status", "set_bypass_mask"):
        assert hass.services.has_service(DOMAIN, service)


async def test_sync_time_sends_the_clock_in_the_panels_own_order(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """`0x55` is **hour first**, which is the reverse of the clock the status frame reports."""
    panel = FakePanel(serial="SYNCTIME01")
    entry = await _writable_entry(hass, port, panel)
    try:
        connection, _ = await _bring_up(hass, entry, connect_panel, panel)
        await hass.services.async_call(
            DOMAIN,
            "sync_time",
            {"device_id": _panel_device_id(hass, entry.entry_id, panel.serial)},
            blocking=True,
        )
        frame = await _next_command(connection)
        assert frame.cmd == Cmd.SET_DATETIME
        # Six BCD bytes: HH MM SS DD MM YY. Every nibble must be a decimal digit.
        payload = frame.raw[4:10]
        assert len(payload) == 6
        assert all(byte >> 4 <= 9 and byte & 0x0F <= 9 for byte in payload)
        assert payload[0] <= 0x23, "an hour, so the first byte is not a day"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_refresh_status_service_asks_the_panel_now(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """A *read*, so it must work through the service call even in read-only mode.

    `setup_entry`/`connect_panel` default to `read_only=True`, which is deliberate here: this is
    the panel-wide equivalent of the refresh button, and both have to work without the commands
    switch being on.
    """
    connection = await connect_panel(panel)
    await connection.introduce(hass)

    await hass.services.async_call(
        DOMAIN,
        "refresh_status",
        {"device_id": _panel_device_id(hass, setup_entry.entry_id, panel.serial)},
        blocking=True,
    )
    reply = await connection.read_reply()
    assert FrameReader().feed(reply)[0].cmd == Cmd.STATUS


async def test_set_bypass_mask_replaces_the_whole_list(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """Including with an empty list, which is how every bypass is cleared."""
    panel = FakePanel(serial="MASKSVC001", zones={1: 0x1, 9: 0x1})
    entry = await _writable_entry(hass, port, panel)
    try:
        connection, _ = await _bring_up(hass, entry, connect_panel, panel)
        device_id = _panel_device_id(hass, entry.entry_id, panel.serial)

        await hass.services.async_call(
            DOMAIN, "set_bypass_mask", {"device_id": device_id, "zones": [3, 4]}, blocking=True
        )
        frame = await _next_command(connection)
        assert bitmap_to_flags(frame.raw[4:17], lsb_first=False) == frozenset({3, 4})

        await hass.services.async_call(
            DOMAIN, "set_bypass_mask", {"device_id": device_id, "zones": []}, blocking=True
        )
        frame = await _next_command(connection)
        assert frame.raw[4:17] == bytes(13), "thirteen zero bytes, as captured"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_service_targeting_a_partition_finds_its_panel(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """Somebody targeting "Partition 1" to set the clock means the panel it is on."""
    panel = FakePanel(serial="SUBDEVICE1")
    entry = await _writable_entry(hass, port, panel)
    try:
        connection, _ = await _bring_up(hass, entry, connect_panel, panel)
        partition = get_sub_device(hass, entry.entry_id, (DOMAIN, f"{panel.serial}-partition1"))
        assert partition is not None

        await hass.services.async_call(
            DOMAIN, "sync_time", {"device_id": partition.id}, blocking=True
        )
        assert (await _next_command(connection)).cmd == Cmd.SET_DATETIME
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_service_on_an_unknown_device_fails_loudly(hass: HomeAssistant) -> None:
    """Never silently: an automation pointed at a deleted panel has to say so."""
    from homeassistant.components.jfl_alarm import async_setup

    assert await async_setup(hass, {})
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "sync_time", {"device_id": "does-not-exist"}, blocking=True
        )


async def test_read_only_mode_stops_the_services_too(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """A gate that only guards the entities is not a gate."""
    connection, _ = await _bring_up(hass, setup_entry, connect_panel, panel)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "set_bypass_mask",
            {"device_id": _panel_device_id(hass, setup_entry.entry_id, panel.serial), "zones": [1]},
            blocking=True,
        )
    with pytest.raises(TimeoutError):
        await connection.read_reply(timeout=0.3)

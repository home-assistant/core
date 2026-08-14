"""Reading the panel's programming through the coordinator, and what it changes in Home Assistant.

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

Sprint 6, tasks 6.2 and 6.4. The frame-level parsing is covered in `tests/test_programming.py`
against real captured bytes; these tests are about the round trip — thirty-odd requests paced over a
live socket, correlated by their echoed selector, and the names that come out the other end.

The one that matters most is `test_a_zone_keeps_its_entity_id_when_it_gains_a_name`. Zone names are
the headline of this sprint and they arrive **after** the entities exist, so the failure mode is not
"no name" — it is every zone entity being renamed out from under the user's automations.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from homeassistant.components.jfl_alarm.const import CONF_READ_ONLY, DOMAIN
from homeassistant.components.jfl_alarm.device import get_sub_device
from tests.components.jfl_alarm.conftest import make_entry
from tests.components.jfl_alarm.panel_sim import FakePanel

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


async def _entry_for(hass: HomeAssistant, port: int, panel: FakePanel, **subentry: object):
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


async def test_a_read_runs_in_read_only_mode(hass: HomeAssistant, port: int, connect_panel) -> None:
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


async def test_zones_and_partitions_take_the_panels_own_names(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The headline of the sprint: `Zone 1 P Frente` instead of `Zone 1`."""
    panel = FakePanel(serial="NAMES00001", **NAMED_PANEL)
    entry = await _entry_for(hass, port, panel)
    try:
        _, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        await coordinator.async_read_programming()

        zone = get_sub_device(hass, entry.entry_id, (DOMAIN, f"{panel.serial}-zone1"))
        assert zone.name == "Zone 1 P Frente"

        # **The name has to come from a translation key, not an f-string.** Composing it literally
        # is what put the English word "Zone" on a Portuguese device page. `DeviceEntry` resolves
        # the key into `name` and does not keep it, so the half of this that an English test run
        # cannot see — that `zone_named` exists in *both* languages with both placeholders — is
        # asserted in `tests/test_translations.py`.

        partition = get_sub_device(hass, entry.entry_id, (DOMAIN, f"{panel.serial}-partition1"))
        assert partition.name == "Interno"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_zone_with_no_programmed_name_stays_a_bare_number(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """**Never `Zone 2 (unnamed)`.** A parenthetical that says nothing is noise on every row.

    Settled in `docs/development/entity-map.md` before the code existed; this holds it.
    """
    panel = FakePanel(serial="NONAME0001", zones={1: 0x8, 2: 0x8}, zone_names={1: "Cozinha"})
    entry = await _entry_for(hass, port, panel)
    try:
        _, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        await coordinator.async_read_programming()

        unnamed = get_sub_device(hass, entry.entry_id, (DOMAIN, f"{panel.serial}-zone2"))
        assert unnamed.name == "Zone 2", "the plain numbered key, still translatable"

        named = get_sub_device(hass, entry.entry_id, (DOMAIN, f"{panel.serial}-zone1"))
        assert named.name == "Zone 1 Cozinha"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_zone_keeps_its_entity_id_when_it_gains_a_name(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The test this task exists in order not to break.

    Names arrive after the entities do. Home Assistant derives an `entity_id` from the device name
    exactly once, at registration, so a zone that gains a name must keep its id — otherwise every
    automation referring to it breaks on the day somebody presses "read programming".
    """
    panel = FakePanel(serial="STABLEID01", **NAMED_PANEL)
    entry = await _entry_for(hass, port, panel)
    try:
        _, coordinator = await _bring_up(hass, entry, connect_panel, panel)

        entities = er.async_get(hass)
        before = entities.async_get_entity_id("binary_sensor", DOMAIN, f"{panel.serial}-zone1-open")
        assert before is not None

        await coordinator.async_read_programming()

        after = entities.async_get_entity_id("binary_sensor", DOMAIN, f"{panel.serial}-zone1-open")
        assert after == before, "the entity_id must not churn when a name appears"
        assert hass.states.get(before) is not None
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_wireless_zone_gains_its_serial(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The enrolment table at `0x1800` is the only place the panel says a zone is a radio device."""
    panel = FakePanel(serial="RADIO00001", **NAMED_PANEL)
    entry = await _entry_for(hass, port, panel)
    try:
        _, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        await coordinator.async_read_programming()

        from homeassistant.components.jfl_alarm.device import _HAS_CHILD_DEVICE_INFO

        radio = get_sub_device(hass, entry.entry_id, (DOMAIN, f"{panel.serial}-zone9"))
        wired = get_sub_device(hass, entry.entry_id, (DOMAIN, f"{panel.serial}-zone1"))
        if _HAS_CHILD_DEVICE_INFO:
            # Child devices carry no `serial_number` field at all; the radio's serial moved to
            # `sensor.py`'s `extra_state_attributes` instead — asserted elsewhere for this HA
            # version.
            pass
        else:
            assert radio.serial_number == f"{0xB205AF2A:010d}"

            # A hard-wired zone gains nothing, and that is correct rather than a gap: the panel does
            # not know what is wired to it.
            assert wired.serial_number is None

        assert coordinator.programming.wireless_for_zone(9) is not None
        assert coordinator.programming.wireless_for_zone(1) is None
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


# --- 6.5: reads only, and no codes ---------------------------------------------------------------


async def test_the_service_response_can_never_carry_an_access_code(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """AGENTS.md §4. The parser discards codes, so the response cannot contain one to leak."""
    panel = FakePanel(serial="NOCODES001", **NAMED_PANEL)
    entry = await _entry_for(hass, port, panel)
    try:
        await _bring_up(hass, entry, connect_panel, panel)
        device = dr.async_get(hass).async_get_device_by_identifier(
            (DOMAIN, panel.serial), config_entry_id=entry.entry_id
        )

        response = await hass.services.async_call(
            DOMAIN,
            "read_programming",
            {"device_id": device.id},
            blocking=True,
            return_response=True,
        )
        assert response["zones"]["1"] == "P Frente"
        assert "code" not in repr(response).lower().replace("has_code", "")
        for user in response["users"]:
            assert set(user) == {"number", "name", "has_code"}
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_nothing_in_this_sprint_can_write(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """Sprint 6 is reads only. `0x45` exists in no code path an entity or service can reach."""
    from homeassistant.components.jfl_alarm import coordinator as coordinator_module

    source = __import__("pathlib").Path(coordinator_module.__file__).read_text(encoding="utf-8")
    assert "WRITE_PROGRAMMING" not in source
    assert "build_programming_write" not in source


@pytest.mark.parametrize("region", ["zones", "partition_names", "users", "pgms", "wireless"])
def test_every_region_is_planned_from_the_documented_map(region: str) -> None:
    """A region whose plan does not start at its base would read somebody else's records."""
    from pyjfl.protocol.programming import REGIONS, plan_region

    requests = plan_region(region)
    assert requests[0].address == REGIONS[region][0]


async def test_a_programmed_name_survives_a_later_entity_registration(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The author's bug, 2026-08-09: a zone name appeared and then reverted minutes later.

    After pressing *Read programming* a device correctly read *Zona 9 Porta 1*, and some time later
    it was back to *Zona 9*. The cause is that `DeviceInfo` is written to the registry **every time
    an entity is added**, and discovery runs again on every coordinator update — so one entity
    constructed with the nameless `build_zone_device` silently overwrote the name that
    `async_apply_programmed_names` had just written.

    Reproducing it needs the second registration, which is why this test adds an entity *after* the
    read rather than asserting on the read alone. `JflZoneEntity` now passes the coordinator's
    current name into its own `DeviceInfo`, so every writer agrees.
    """
    panel = FakePanel(serial="STICKYNAM1", **NAMED_PANEL)
    entry = await _entry_for(hass, port, panel)
    try:
        _, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        await coordinator.async_read_programming()

        devices = dr.async_get(hass)
        named = get_sub_device(hass, entry.entry_id, (DOMAIN, f"{panel.serial}-zone9"))
        assert named.name_by_user is None
        before = named.name

        # A fresh entity for the same zone, built the way discovery builds one.
        from homeassistant.components.jfl_alarm.binary_sensor import JflZoneSensor

        entity = JflZoneSensor(coordinator, 9)
        device_info = entity.device_info
        assert device_info is not None
        # Mirrors the dispatch `entity_platform.py` itself makes when a real entity registers: a
        # `parent_device_id` means a child device (2026.9+), and `async_get_or_create` is
        # main-device only from that version on.
        if device_info.get("parent_device_id") is not None:
            devices.async_get_or_create_child(  # type: ignore[attr-defined]
                config_entry_id=entry.entry_id,
                config_subentry_id=coordinator.subentry.subentry_id,
                **device_info,
            )
        else:
            devices.async_get_or_create(
                config_entry_id=entry.entry_id,
                config_subentry_id=coordinator.subentry.subentry_id,
                **device_info,
            )
        await hass.async_block_till_done()

        after = get_sub_device(hass, entry.entry_id, (DOMAIN, f"{panel.serial}-zone9"))
        assert after.name == before, "a later registration must not strip the programmed name"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_wireless_zone_gains_signal_and_last_transmission_entities(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """Sprint 8.6's other half: the detector's live condition, not just its enrolment.

    The `0x59` inventory is a separate command from a programming read — the panel's own UI leaves
    these columns blank until somebody presses *Atualizar*, which is the same request. So the
    entities can only appear after the coordinator has asked, and this test is what proves it asks.
    """
    panel = FakePanel(serial="RADIOLIVE1", **NAMED_PANEL)
    entry = await _entry_for(hass, port, panel)
    try:
        _, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        await coordinator.async_read_programming()
        await hass.async_block_till_done()

        assert coordinator.programming.inventory, "the inventory must have been fetched"

        entities = er.async_get(hass)
        signal_id = entities.async_get_entity_id("sensor", DOMAIN, f"{panel.serial}-zone9-signal")
        assert signal_id is not None, "the signal sensor must exist for a wireless zone"
        signal = hass.states.get(signal_id)
        assert signal is not None
        assert signal.state in {"excellent", "very_good", "good", "weak", "none"}
        assert signal.attributes["firmware"] == "4.0"
        assert "repeater" in signal.attributes

        last_id = entities.async_get_entity_id(
            "sensor", DOMAIN, f"{panel.serial}-zone9-last_transmission"
        )
        assert last_id is not None
        last_seen = hass.states.get(last_id)
        assert last_seen is not None
        assert last_seen.state.startswith("09/08/26")

        # A hard-wired zone has no radio device, so it gets neither entity.
        assert (
            entities.async_get_entity_id("sensor", DOMAIN, f"{panel.serial}-zone1-signal") is None
        )
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_the_timers_become_diagnostic_sensors(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """Sprint 8.4: the timers carry their own units, which is the whole trap.

    Entry and exit are seconds while open-door is minutes, so a suite that only checked the numbers
    would pass on an implementation that is wrong by a factor of sixty.
    """
    panel = FakePanel(serial="TIMERSPAN1", **NAMED_PANEL)
    entry = await _entry_for(hass, port, panel)
    try:
        _, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        await coordinator.async_read_programming()
        await hass.async_block_till_done()

        entry_1 = hass.states.get("sensor.active_32_duo_entry_delay_1")
        open_door = hass.states.get("sensor.active_32_duo_open_door_time")
        assert entry_1 is not None, "the timer sensors must exist after a programming read"
        assert open_door is not None
        assert entry_1.attributes["unit_of_measurement"] == "s"
        assert open_door.attributes["unit_of_measurement"] == "min"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

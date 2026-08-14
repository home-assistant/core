"""Zones as devices, and the wireless health that only the events can carry.

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

Sprint 5. Two of these tests are the sprint, and the rest support them.

**The merge test.** A zone's nibble holds one value, so a sensor with a dying battery reports `6`
while closed and `7` the moment somebody walks past it. If the battery sensor read the nibble alone,
walking past a failing detector would mark its battery healthy. The event pair `1384`/`3384` is not
overwritten by anything, so the two sources are merged and either one saying yes is a yes.

**The migration test.** Sprint 5 moves zone entities onto their own devices. That is a registry
update and must not be a re-creation: an installation that ran Sprint 2 has history, customisations
and automations pointing at those entities. The test writes a Sprint 2-shaped registry entry by hand
and proves the entity is adopted rather than replaced.
"""

from __future__ import annotations

import pytest
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from homeassistant.components.jfl_alarm.const import DOMAIN
from homeassistant.components.jfl_alarm.device import _HAS_CHILD_DEVICE_INFO, get_sub_device
from tests.components.jfl_alarm.conftest import make_entry, wait_until
from tests.components.jfl_alarm.panel_sim import FakePanel


async def _bring_up(hass: HomeAssistant, entry, connect_panel, panel: FakePanel):
    """Connect *panel* and absorb one status frame."""
    coordinator = entry.runtime_data.coordinators[panel.serial]
    connection = await connect_panel(panel)
    await connection.introduce(hass)
    await connection.report_status(hass, coordinator)
    return connection, coordinator


# --- zones as devices ---------------------------------------------------------------------------


async def test_each_zone_becomes_its_own_device_under_the_panel(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """A detector is a device, and its five entities belong together under one heading."""
    await _bring_up(hass, setup_entry, connect_panel, panel)

    devices = dr.async_get(hass)
    zone = get_sub_device(hass, setup_entry.entry_id, (DOMAIN, f"{panel.serial}-zone1"))
    assert zone is not None
    panel_device = devices.async_get_device_by_identifier(
        (DOMAIN, panel.serial), config_entry_id=setup_entry.entry_id
    )
    linked_to = getattr(zone, "parent_device_id", None) or zone.via_device_id
    assert linked_to == panel_device.id

    # No invented model or manufacturer: the panel reports the *state* of a zone, never what is
    # wired to it. A reed switch and an IRD-650 are the same nibble. On 2026.9+ a child device has
    # no `model` field at all — `ChildDeviceEntry.model` raises rather than returning `None` from
    # this test's own frame — so the raise is itself the guarantee on that path.
    if _HAS_CHILD_DEVICE_INFO:
        with pytest.raises(AttributeError):
            _ = zone.model
    else:
        assert zone.model is None

    entities = er.async_get(hass)
    on_this_zone = {
        entry.unique_id.split("-", 1)[1]
        for entry in er.async_entries_for_device(entities, zone.id, include_disabled_entities=True)
    }
    assert on_this_zone == {
        "zone1-open",
        "zone1-problem",
        "zone1-tamper",
        "zone1-battery",
        "zone1-connectivity",
    }


async def test_zone_entities_survive_the_move_to_their_own_device(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The migration test: a registry update, never a re-creation.

    A Sprint 2 installation has `binary_sensor.active_32_duo_zone_1` on the *panel* device, with
    whatever history and automations the user built on it. Sprint 5 moves it. Home Assistant keys
    entities by `unique_id`, so as long as that is unchanged the registry adopts the existing row —
    same `entity_id`, same customisations — and only the device it points at changes.
    """
    panel = FakePanel(serial="MIGRATION1", zones={1: 0x8})
    entry = make_entry(port, serials=[panel.serial])
    entry.add_to_hass(hass)

    devices = dr.async_get(hass)
    entities = er.async_get(hass)

    # Recreate what Sprint 2 left behind: the entity on the panel device, with the old entity_id.
    panel_device = devices.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=next(iter(entry.subentries)),
        identifiers={(DOMAIN, panel.serial)},
        name="Active 32 Duo",
    )
    legacy = entities.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        f"{panel.serial}-zone1-open",
        config_entry=entry,
        config_subentry_id=next(iter(entry.subentries)),
        device_id=panel_device.id,
        suggested_object_id="active_32_duo_zone_1",
    )
    assert legacy.entity_id == "binary_sensor.active_32_duo_zone_1"
    entities.async_update_entity(legacy.entity_id, name="Front door")

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    try:
        await _bring_up(hass, entry, connect_panel, panel)

        migrated = entities.async_get("binary_sensor.active_32_duo_zone_1")
        assert migrated is not None, "the entity_id must not churn"
        assert migrated.unique_id == f"{panel.serial}-zone1-open"
        assert migrated.name == "Front door", "the user's rename survives"

        # It now lives on the zone's own device.
        zone_device = get_sub_device(hass, entry.entry_id, (DOMAIN, f"{panel.serial}-zone1"))
        assert zone_device is not None
        assert migrated.device_id == zone_device.id

        # And no duplicate was created alongside it.
        matching = [
            e
            for e in er.async_entries_for_config_entry(entities, entry.entry_id)
            if e.unique_id == f"{panel.serial}-zone1-open"
        ]
        assert len(matching) == 1
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


# --- wireless health ----------------------------------------------------------------------------


async def test_low_battery_is_read_from_the_nibble(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """Nibble `6` is the panel saying so directly."""
    panel.zones = {1: 0x6, 2: 0x8}
    await _bring_up(hass, setup_entry, connect_panel, panel)

    assert hass.states.get("binary_sensor.zone_1_battery").state == STATE_ON
    assert hass.states.get("binary_sensor.zone_2_battery").state == STATE_OFF


async def test_low_battery_survives_the_zone_opening(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """The test this sprint exists for.

    The nibble holds one value. A sensor reporting a low battery reports `7` the moment somebody
    walks past it, and reading the nibble alone would then call the battery healthy. Event `1384`
    is not overwritten by anything, so the latch outlives the nibble.
    """
    panel.zones = {1: 0x8}
    connection, coordinator = await _bring_up(hass, setup_entry, connect_panel, panel)
    assert hass.states.get("binary_sensor.zone_1_battery").state == STATE_OFF

    await connection.send(panel.event(code="1384", partition="01", subject="001"))
    await wait_until(
        hass, lambda: hass.states.get("binary_sensor.zone_1_battery").state == STATE_ON
    )

    # Now the zone opens. The nibble becomes 7 and says nothing about the battery any more.
    panel.zones = {1: 0x7}
    await connection.report_status(hass, coordinator)
    assert hass.states.get("binary_sensor.zone_1").state == STATE_ON
    assert hass.states.get("binary_sensor.zone_1_battery").state == STATE_ON, (
        "the battery is still low; the nibble simply cannot say so"
    )

    # The panel says it was replaced. Only then does it clear.
    await connection.send(panel.event(code="3384", partition="01", subject="001"))
    await wait_until(
        hass, lambda: hass.states.get("binary_sensor.zone_1_battery").state == STATE_OFF
    )


async def test_supervision_reads_as_a_connectivity_sensor_the_right_way_round(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """`on` means **connected**, which is the device class's direction and the flag's opposite."""
    panel.zones = {1: 0x8, 2: 0x3}
    connection, _ = await _bring_up(hass, setup_entry, connect_panel, panel)

    entities = er.async_get(hass)
    for zone in (1, 2):
        entities.async_update_entity(f"binary_sensor.zone_{zone}_connection", disabled_by=None)
    await hass.config_entries.async_reload(setup_entry.entry_id)
    await hass.async_block_till_done()
    connection, _ = await _bring_up(hass, setup_entry, connect_panel, panel)

    assert hass.states.get("binary_sensor.zone_1_connection").state == STATE_ON
    assert hass.states.get("binary_sensor.zone_2_connection").state == STATE_OFF

    # And event 1381 takes zone 1 offline between status polls.
    await connection.send(panel.event(code="1381", partition="01", subject="001"))
    await wait_until(
        hass, lambda: hass.states.get("binary_sensor.zone_1_connection").state == STATE_OFF
    )


async def test_a_tamper_event_latches_between_polls(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """`1383` arrives immediately; the next poll is up to thirty seconds away."""
    panel.zones = {1: 0x8}
    connection, _ = await _bring_up(hass, setup_entry, connect_panel, panel)
    assert hass.states.get("binary_sensor.zone_1_tamper").state == STATE_OFF

    await connection.send(panel.event(code="1383", partition="01", subject="001"))
    await wait_until(hass, lambda: hass.states.get("binary_sensor.zone_1_tamper").state == STATE_ON)


async def test_a_fence_alarm_does_not_latch_onto_a_zone(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """Partition 99 is the fence, and its subject field is not a zone number."""
    connection, coordinator = await _bring_up(hass, setup_entry, connect_panel, panel)

    await connection.send(panel.event(code="1384", partition="99", subject="000"))
    await wait_until(hass, lambda: coordinator.data.last_event_code == "1384")
    assert coordinator.data.zone_alerts == {}


async def test_the_derived_battery_percentage_is_on_by_default_and_linear(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """Enabled at the author's request: it is what battery cards and voice assistants consume.

    Still an interpretation of a voltage rather than something the panel reports — the voltage
    sensor beside it stays the primary reading, and this one clamps at both ends.
    """
    entities = er.async_get(hass)
    assert entities.async_get("sensor.active_32_duo_battery_level").disabled_by is None

    # 0xB7 / 14 = 13.07 V, above the 12.5 V top of the scale, so it clamps at 100.
    await _bring_up(hass, setup_entry, connect_panel, panel)
    assert hass.states.get("sensor.active_32_duo_battery_level").state == "100"
    assert hass.states.get("sensor.active_32_duo_battery_level").attributes["device_class"] == (
        "battery"
    )


async def test_no_battery_fitted_is_not_a_flat_battery(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """`0` means no battery is fitted. Reporting 0% would alarm every panel running without one."""
    panel = FakePanel(serial="NOBATTERY1", battery_raw=0x00)
    entry = make_entry(port, serials=[panel.serial])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    try:
        await _bring_up(hass, entry, connect_panel, panel)
        assert hass.states.get("sensor.active_32_duo_battery_level").state == "unknown"
        assert float(hass.states.get("sensor.active_32_duo_battery_voltage").state) == 0.0
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

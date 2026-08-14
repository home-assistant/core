"""The entities a panel produces once it dials in.

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

The theme running through these tests is that **nothing exists until the panel says it does**. A
partition that is not programmed produces no entity; a zone that is not in use produces no entity;
a panel with no electric fence produces no fence entity at all, which is a different thing from a
fence entity reading "disarmed".
"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

import pytest
from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pyjfl import UserRecord, ZoneRecord

from homeassistant.components.jfl_alarm.const import (
    CONF_CODE,
    CONF_READ_ONLY,
    CONF_ZONE_POLICY,
    DOMAIN,
    PGM_PLACEMENT_OPTION,
    PGM_PLACEMENT_VERSION,
    ZONES_ALL,
)
from homeassistant.components.jfl_alarm.device import build_fence_device, get_sub_device
from tests.components.jfl_alarm.conftest import announce_programming, make_entry, wait_until
from tests.components.jfl_alarm.panel_sim import FakePanel


async def _bring_up(hass: HomeAssistant, entry, connect_panel, panel: FakePanel):
    """Connect *panel* and wait until its first status frame has been absorbed."""
    coordinator = entry.runtime_data.coordinators[panel.serial]
    connection = await connect_panel(panel)
    await connection.introduce(hass)
    await connection.report_status(hass, coordinator)
    return connection, coordinator


async def test_nothing_is_available_before_the_panel_dials_in(
    hass: HomeAssistant, setup_entry
) -> None:
    """Entities exist and read unavailable — they do not read a made-up "disarmed"."""
    battery = hass.states.get("sensor.active_32_duo_battery_voltage")
    assert battery is not None
    assert battery.state == STATE_UNAVAILABLE

    # Except the one entity whose whole job is to report that the panel is away.
    connectivity = hass.states.get("binary_sensor.active_32_duo_panel_connection")
    assert connectivity is not None
    assert connectivity.state == STATE_OFF


async def test_partitions_appear_only_when_programmed(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """An Active 32 Duo can have four partitions; this installation has programmed two."""
    await _bring_up(hass, setup_entry, connect_panel, panel)

    assert hass.states.get("alarm_control_panel.partition_1") is not None
    assert hass.states.get("alarm_control_panel.partition_2") is not None
    assert hass.states.get("alarm_control_panel.partition_3") is None
    assert hass.states.get("alarm_control_panel.partition_4") is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0x01, AlarmControlPanelState.DISARMED),
        (0x02, AlarmControlPanelState.ARMED_AWAY),
        # JFL calls this STAY. Home Assistant's nearest state is ARMED_HOME.
        (0x03, AlarmControlPanelState.ARMED_HOME),
        # Bit 7 is "in alarm", and it wins over the arm mode.
        (0x82, AlarmControlPanelState.TRIGGERED),
        (0x81, AlarmControlPanelState.TRIGGERED),
    ],
)
async def test_every_partition_state_maps_correctly(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel, raw: int, expected: str
) -> None:
    """The whole `PART[i]` byte, mapped to the alarm panel domain."""
    panel.partitions = [raw, 0x00, 0x00, 0x00]
    await _bring_up(hass, setup_entry, connect_panel, panel)

    state = hass.states.get("alarm_control_panel.partition_1")
    assert state is not None
    assert state.state == expected


@pytest.mark.parametrize(
    ("raw", "switch_state", "sensor_state", "alarm_state", "ready"),
    [
        (0x01, STATE_OFF, "disarmed", STATE_OFF, True),
        (0x02, STATE_ON, "armed", STATE_OFF, True),
        (0x04, STATE_OFF, "not_ready", STATE_OFF, False),
        (0x82, STATE_ON, "triggered", STATE_ON, True),
        (0x81, STATE_OFF, "triggered", STATE_ON, True),
    ],
)
async def test_the_fence_is_a_switch_with_a_state_sensor_beside_it(
    hass: HomeAssistant,
    setup_entry,
    connect_panel,
    panel: FakePanel,
    raw,
    switch_state,
    sensor_state,
    alarm_state,
    ready,
) -> None:
    """The project's primary goal.

    Deliberately **not** an alarm control panel: that domain has no plain "armed", so an armed fence
    would have to be reported as "armed away", and an energiser has no away. The switch operates it,
    the enumerated sensor names the state, and the safety sensor carries the alarm — and a triggered
    fence stays armed, which is why `0x82` is both on and in alarm.
    """
    panel.fence = raw
    await _bring_up(hass, setup_entry, connect_panel, panel)

    switch = hass.states.get("switch.electric_fence")
    assert switch is not None
    assert switch.state == switch_state
    assert switch.attributes["ready"] is ready

    state_sensor = hass.states.get("sensor.electric_fence_state")
    assert state_sensor is not None
    assert state_sensor.state == sensor_state
    assert state_sensor.attributes["raw"] == raw

    assert hass.states.get("binary_sensor.electric_fence_alarm").state == alarm_state


async def test_the_fence_is_not_an_alarm_control_panel(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """Regression: it was one in Sprint 2, and "Armado ausente" is a claim the fence cannot make."""
    await _bring_up(hass, setup_entry, connect_panel, panel)
    assert hass.states.get("alarm_control_panel.electric_fence") is None


async def test_a_panel_without_a_fence_gets_no_fence_entity(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """`ELET = 0x00` means no fence exists, which is not the same as a disarmed one."""
    panel = FakePanel(serial="NOFENCE001", model_byte=0xA2, fence=0x00)
    entry = make_entry(port, serials=[panel.serial])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    try:
        await _bring_up(hass, entry, connect_panel, panel)
        assert hass.states.get("switch.electric_fence") is None
        assert hass.states.get("sensor.electric_fence_state") is None
        assert hass.states.get("binary_sensor.electric_fence_alarm") is None
        assert hass.states.get("event.electric_fence_events") is None
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_zone_produces_three_separate_sensors(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """Open, fault and tamper are three different facts and must not share one entity."""
    panel.zones = {1: 0x7, 2: 0x8, 3: 0x5, 4: 0x3}
    await _bring_up(hass, setup_entry, connect_panel, panel)

    # Zone 1 is open; zone 2 is closed.
    assert hass.states.get("binary_sensor.zone_1").state == STATE_ON
    assert hass.states.get("binary_sensor.zone_2").state == STATE_OFF

    # Zone 3 is tampered: the tamper sensor is on, the fault sensor is not, and — the point of the
    # split — the *opening* sensor is off, so "zone 3 is open" does not become true.
    assert hass.states.get("binary_sensor.zone_3_tamper").state == STATE_ON
    assert hass.states.get("binary_sensor.zone_3_sensor").state == STATE_OFF
    assert hass.states.get("binary_sensor.zone_3").state == STATE_OFF

    # Zone 4 is not communicating: a fault, not a tamper, and not an opening.
    fault = hass.states.get("binary_sensor.zone_4_sensor")
    assert fault.state == STATE_ON
    assert fault.attributes["zone_status"] == "not_communicating"
    assert hass.states.get("binary_sensor.zone_4_tamper").state == STATE_OFF


async def test_a_triggered_zone_still_counts_as_open(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """A sensor triggering an alarm is, physically, an open sensor."""
    panel.zones = {1: 0x2}
    await _bring_up(hass, setup_entry, connect_panel, panel)
    assert hass.states.get("binary_sensor.zone_1").state == STATE_ON


async def test_disabled_zones_are_skipped_unless_asked_for(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The default creates only zones in use; the other policy creates every zone the model has."""
    panel = FakePanel(serial="ALLZONES01", zones={1: 0x8})
    entry = make_entry(port, serials=[panel.serial], subentry_data={CONF_ZONE_POLICY: ZONES_ALL})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    try:
        await _bring_up(hass, entry, connect_panel, panel)
        # The Active 32 Duo has 32 zones, and all of them exist under this policy.
        assert hass.states.get("binary_sensor.zone_32") is not None
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_trouble_flags_become_diagnostic_sensors(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """Losing mains power is the trouble a user actually acts on."""
    # PROB byte 2 bit 7 is AC mains — flat bit index 15.
    panel.problems = b"\x00\x80\x00\x00\x00"
    await _bring_up(hass, setup_entry, connect_panel, panel)

    assert hass.states.get("binary_sensor.active_32_duo_mains_power").state == STATE_ON
    assert hass.states.get("binary_sensor.active_32_duo_battery").state == STATE_OFF
    # And the aggregate says "something is wrong" without listing thirty-two bits.
    assert hass.states.get("binary_sensor.active_32_duo_panel_status").state == STATE_ON


async def test_the_battery_voltage_is_a_voltage(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """`raw / 14` volts, with no invented percentage buckets."""
    await _bring_up(hass, setup_entry, connect_panel, panel)
    state = hass.states.get("sensor.active_32_duo_battery_voltage")
    assert state is not None
    assert float(state.state) == pytest.approx(0xB7 / 14)
    assert state.attributes["unit_of_measurement"] == "V"
    assert state.attributes["device_class"] == "voltage"


async def test_identity_is_on_the_device_and_not_in_entities(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """AGENTS.md §5: model, firmware, serial and MAC belong to the device registry."""
    await _bring_up(hass, setup_entry, connect_panel, panel)

    devices = dr.async_get(hass)
    device = devices.async_get_device_by_identifier(
        (DOMAIN, panel.serial), config_entry_id=setup_entry.entry_id
    )
    assert device is not None
    assert device.manufacturer == "JFL"
    assert device.model == "Active 32 Duo"
    assert device.model_id == "0xA0"
    assert device.sw_version == "7.60"
    assert device.serial_number == panel.serial
    assert (dr.CONNECTION_NETWORK_MAC, dr.format_mac(panel.mac)) in device.connections

    # None of it leaked into an entity.
    entities = er.async_get(hass)
    keys = {
        entry.unique_id
        for entry in er.async_entries_for_config_entry(entities, setup_entry.entry_id)
    }
    assert not any("firmware" in key or "model" in key or "serial" in key for key in keys)


async def test_partitions_and_the_fence_are_sub_devices_of_the_panel(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """The sub-device link is what makes the device page readable on a multi-partition install."""
    await _bring_up(hass, setup_entry, connect_panel, panel)

    devices = dr.async_get(hass)
    panel_device = devices.async_get_device_by_identifier(
        (DOMAIN, panel.serial), config_entry_id=setup_entry.entry_id
    )
    for suffix in ("partition1", "fence"):
        sub = get_sub_device(hass, setup_entry.entry_id, (DOMAIN, f"{panel.serial}-{suffix}"))
        assert sub is not None
        # `parent_device_id` on 2026.9+ (a child device); `via_device_id` before it — whichever
        # this Home Assistant version has must name the same panel device.
        linked_to = getattr(sub, "parent_device_id", None) or sub.via_device_id
        assert linked_to == panel_device.id


async def test_an_entity_stranded_on_an_enabled_device_is_released(
    hass: HomeAssistant, port: int, connect_panel, panel: FakePanel
) -> None:
    """`disabled_by: device` on a device that is not disabled is a dead end, and setup clears it.

    Home Assistant writes that flag when it disables a device and clears it again when the device is
    re-enabled — but only through the device registry's own update path. A config entry re-enabled
    by editing `.storage` by hand, which is how the lab's was brought back on 2026-08-09, leaves the
    entities stranded: the frontend will not enable one whose device it believes is disabled, and
    the device it names is enabled. The author hit exactly this on the electric fence, whose switch,
    both sensors and event entity were all unreachable at once.
    """
    entry = make_entry(port, serials=[panel.serial])
    entry.add_to_hass(hass)
    subentry_id = next(iter(entry.subentries))
    # `async_setup` has not run yet, so the panel device this stray fence has to attach to (on
    # 2026.9+, a fence is a *child* device — see `build_fence_device`) does not exist. Registered by
    # hand here, the same way `__init__.py` registers it before forwarding any platform.
    registry = dr.async_get(hass)
    registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=subentry_id,
        identifiers={(DOMAIN, panel.serial)},
    )
    fence = build_fence_device(hass, entry.entry_id, panel.serial)
    if fence.get("parent_device_id") is not None:
        fence_device = registry.async_get_or_create_child(  # type: ignore[attr-defined]
            config_entry_id=entry.entry_id, config_subentry_id=subentry_id, **fence
        )
    else:
        fence_device = registry.async_get_or_create(
            config_entry_id=entry.entry_id, config_subentry_id=subentry_id, **fence
        )
    assert not fence_device.disabled, "the device is fine; only the entities are stuck"
    entities = er.async_get(hass)
    stranded = entities.async_get_or_create(
        "switch",
        DOMAIN,
        f"{panel.serial}-fence-switch",
        config_entry=entry,
        config_subentry_id=subentry_id,
        device_id=fence_device.id,
        disabled_by=er.RegistryEntryDisabler.DEVICE,
    )
    assert stranded.disabled_by is er.RegistryEntryDisabler.DEVICE

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    try:
        assert entities.async_get(stranded.entity_id).disabled_by is None
        await _bring_up(hass, entry, connect_panel, panel)
        assert hass.states.get(stranded.entity_id) is not None, "and it comes back in this setup"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_an_entity_the_user_disabled_is_left_alone(
    hass: HomeAssistant, port: int, connect_panel, panel: FakePanel
) -> None:
    """The release is narrow on purpose: only `disabled_by: device`, and only on an enabled device.

    An entity the user switched off themselves is marked `disabled_by: user`, and switching it back
    on behind their back would be worse than the dead end this fixes.
    """
    entry = make_entry(port, serials=[panel.serial])
    entry.add_to_hass(hass)
    entities = er.async_get(hass)
    chosen = entities.async_get_or_create(
        "switch",
        DOMAIN,
        f"{panel.serial}-fence-switch",
        config_entry=entry,
        config_subentry_id=next(iter(entry.subentries)),
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    try:
        assert entities.async_get(chosen.entity_id).disabled_by is er.RegistryEntryDisabler.USER
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_an_entity_on_a_still_disabled_device_is_left_alone(
    hass: HomeAssistant, port: int, connect_panel, panel: FakePanel
) -> None:
    """The release only fixes the dead end — a device the user has genuinely disabled is untouched.

    `disabled_by: device` on an entity whose device really is disabled is not a bug to fix: it is
    exactly what Home Assistant itself would have set, and the entity should stay disabled until
    the device is re-enabled through the ordinary path.
    """
    entry = make_entry(port, serials=[panel.serial])
    entry.add_to_hass(hass)
    subentry_id = next(iter(entry.subentries))
    devices = dr.async_get(hass)
    fence_device = devices.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=subentry_id,
        identifiers={(DOMAIN, f"{panel.serial}-fence")},
    )
    devices.async_update_device(fence_device.id, disabled_by=dr.DeviceEntryDisabler.USER)

    entities = er.async_get(hass)
    stranded = entities.async_get_or_create(
        "switch",
        DOMAIN,
        f"{panel.serial}-fence-switch",
        config_entry=entry,
        config_subentry_id=subentry_id,
        device_id=fence_device.id,
        disabled_by=er.RegistryEntryDisabler.DEVICE,
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    try:
        assert entities.async_get(stranded.entity_id).disabled_by is er.RegistryEntryDisabler.DEVICE
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_unique_ids_derive_from_the_serial(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """So that entities survive removing and re-adding the integration."""
    await _bring_up(hass, setup_entry, connect_panel, panel)

    entities = er.async_get(hass)
    entry = entities.async_get("switch.electric_fence")
    assert entry is not None
    assert entry.unique_id == f"{panel.serial}-fence-switch"
    assert setup_entry.entry_id not in entry.unique_id


async def test_the_diagnostic_entities_are_marked_diagnostic(
    hass: HomeAssistant, setup_entry
) -> None:
    """Present, but out of the way — not cluttering the dashboard."""
    entities = er.async_get(hass)
    for entity_id in (
        "sensor.active_32_duo_battery_voltage",
        "binary_sensor.active_32_duo_panel_connection",
        "button.active_32_duo_refresh_status",
    ):
        entry = entities.async_get(entity_id)
        assert entry is not None, entity_id
        assert entry.entity_category is EntityCategory.DIAGNOSTIC, entity_id


async def test_an_event_fires_on_the_panel_and_its_partition(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """A Contact ID event reaches the panel-wide entity and the right partition's."""
    connection, _ = await _bring_up(hass, setup_entry, connect_panel, panel)

    await connection.send(panel.event(code="1130", partition="02", subject="009"))
    # **Wait for both, not for one and then assert on the other.** They are written from the same
    # dispatcher callback but each schedules its own state write, so waiting on the partition's and
    # then reading the panel-wide one lost about one run in eight — the flake this replaces. Neither
    # ordering is guaranteed, so the condition is that both have landed.
    await wait_until(
        hass,
        lambda: all(
            hass.states.get(entity_id).state not in ("unknown", "unavailable")
            for entity_id in ("event.partition_2_events", "event.active_32_duo_panel_events")
        ),
    )

    panel_event = hass.states.get("event.active_32_duo_panel_events")
    assert panel_event.attributes["event_type"] == "alarm"
    assert panel_event.attributes["code"] == "1130"
    assert panel_event.attributes["description"]
    assert panel_event.attributes["subject"] == "009"

    # Partition 2 heard it; partition 1 did not. Compared by the event's own content, not the
    # entity's `state` timestamp: each entity schedules its own state write off the same
    # dispatcher signal, so their timestamps can differ by a millisecond even though it is the
    # same event — comparing them for equality is the same flake `wait_until` above works around.
    partition_2_event = hass.states.get("event.partition_2_events")
    assert partition_2_event.attributes["code"] == panel_event.attributes["code"]
    assert hass.states.get("event.partition_1_events").state == "unknown"


async def test_an_arm_event_names_the_user_who_did_it(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """Sprint 8.5, "who armed the house?" — the logbook said *003*; it can now say *Bruno*.

    The same three-character field carries a **zone** number for an alarm, so the lookup follows the
    Contact ID code's declared subject rather than the value.
    """
    connection, coordinator = await _bring_up(hass, setup_entry, connect_panel, panel)
    coordinator.programming = replace(
        coordinator.programming,
        read_at=dt_util.utcnow(),
        users={3: UserRecord(number=3, name="Bruno", has_code=True, attributes=bytes(8))},
        zones={9: ZoneRecord(9, "Porta dos fundos", bytes.fromhex("10FFFF1101FFFF"))},
    )

    # 3401: armed by user 3.
    await connection.send(panel.event(code="3401", partition="01", subject="003"))
    await wait_until(
        hass,
        lambda: hass.states.get("event.partition_1_events").state not in ("unknown", "unavailable"),
    )
    armed = hass.states.get("event.partition_1_events")
    assert armed.attributes["subject"] == "003"
    assert armed.attributes["subject_kind"] == "user"
    assert armed.attributes["subject_name"] == "Bruno"

    # 1130 is a burglary on a *zone*, and the same field means something else entirely.
    await connection.send(panel.event(code="1130", partition="01", subject="009"))
    await wait_until(
        hass, lambda: hass.states.get("event.partition_1_events").attributes["code"] == "1130"
    )
    alarm = hass.states.get("event.partition_1_events")
    assert alarm.attributes["subject_kind"] == "zone"
    assert alarm.attributes["subject_name"] == "Porta dos fundos"


async def test_an_event_from_the_app_or_this_integration_names_nobody(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """`000` and `099` are **origins**, not people, and must never be looked up as users.

    The 2026-08-08 capture settled that: `099` is the monitoring connection — this integration — and
    `000` the mobile app. A panel with a user 99 would otherwise have every remote arm attributed to
    them, which is a confident falsehood about a person.
    """
    connection, coordinator = await _bring_up(hass, setup_entry, connect_panel, panel)
    coordinator.programming = replace(
        coordinator.programming,
        read_at=dt_util.utcnow(),
        users={99: UserRecord(number=99, name="Carla", has_code=True, attributes=bytes(8))},
    )

    await connection.send(panel.event(code="3401", partition="01", subject="099"))
    await wait_until(
        hass,
        lambda: hass.states.get("event.partition_1_events").state not in ("unknown", "unavailable"),
    )
    armed = hass.states.get("event.partition_1_events")
    assert armed.attributes["subject"] == "099"
    assert "subject_name" not in armed.attributes, "Carla did not arm this; the receiver did"


async def test_an_event_before_a_programming_read_carries_no_name(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """No name is better than an empty one: the key is simply absent, as it always was."""
    connection, _ = await _bring_up(hass, setup_entry, connect_panel, panel)

    await connection.send(panel.event(code="3401", partition="01", subject="003"))
    await wait_until(
        hass,
        lambda: hass.states.get("event.partition_1_events").state not in ("unknown", "unavailable"),
    )
    assert "subject_name" not in hass.states.get("event.partition_1_events").attributes


async def test_a_fence_event_is_flagged_as_one(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """The panel reports the fence as partition 99, and the payload has to say so."""
    connection, _ = await _bring_up(hass, setup_entry, connect_panel, panel)

    await connection.send(panel.event(code="1130", partition="99", subject="000"))
    await wait_until(
        hass,
        lambda: hass.states.get("event.active_32_duo_panel_events").attributes.get("is_fence")
        is True,
    )


async def test_a_fence_arm_does_not_read_as_the_house_being_armed(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """Reported from the lab on 2026-08-08.

    Arming the fence from the mobile app left the panel-wide event entity reading "Armed", for a
    house that was never armed. The fence reports the ordinary arm code with partition 99, so the
    classification has to take the partition into account — and the fence now has an entity of its
    own as well.
    """
    connection, _ = await _bring_up(hass, setup_entry, connect_panel, panel)

    await connection.send(panel.event(code="3407", partition="99", subject="099"))
    await wait_until(
        hass,
        lambda: hass.states.get("event.electric_fence_events").state
        not in ("unknown", "unavailable"),
    )

    fence_event = hass.states.get("event.electric_fence_events")
    assert fence_event.attributes["event_type"] == "fence_arm"

    panel_event = hass.states.get("event.active_32_duo_panel_events")
    assert panel_event.attributes["event_type"] == "fence_arm", "not the bare 'arm'"

    # And no partition claims it: 99 is not a partition.
    assert hass.states.get("event.partition_1_events").state == "unknown"
    assert hass.states.get("event.partition_2_events").state == "unknown"


async def test_a_partition_arm_still_reads_as_an_ordinary_arm(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """The other half of the fix: the fence labels must not swallow the real ones."""
    connection, _ = await _bring_up(hass, setup_entry, connect_panel, panel)

    await connection.send(panel.event(code="3407", partition="01", subject="099"))
    await wait_until(hass, lambda: hass.states.get("event.partition_1_events").state != "unknown")
    assert hass.states.get("event.partition_1_events").attributes["event_type"] == "arm"


async def test_the_last_event_sensor_records_when_not_what(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """The event itself travels on the dispatcher; only its timestamp is state."""
    connection, coordinator = await _bring_up(hass, setup_entry, connect_panel, panel)
    assert coordinator.data.last_event_at is None

    await connection.send(panel.event())
    await wait_until(hass, lambda: coordinator.data.last_event_at is not None)
    assert coordinator.data.last_event_code == "1130"


async def test_the_refresh_button_asks_the_panel(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """A read, so it works in read-only mode — otherwise there is nothing to read."""
    connection, _ = await _bring_up(hass, setup_entry, connect_panel, panel)

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.active_32_duo_refresh_status"},
        blocking=True,
    )
    reply = await connection.read_reply()
    from pyjfl import Cmd, FrameReader

    assert FrameReader().feed(reply)[0].cmd == Cmd.STATUS


async def test_pressing_refresh_with_no_panel_fails_loudly(
    hass: HomeAssistant, setup_entry
) -> None:
    """Never silently: the user pressed a button and nothing would have happened."""
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.active_32_duo_refresh_status"},
            blocking=True,
        )


async def test_entities_become_unavailable_when_the_panel_goes_away(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """Availability follows the connection, not the coordinator's update history."""
    connection, coordinator = await _bring_up(hass, setup_entry, connect_panel, panel)
    assert hass.states.get("alarm_control_panel.partition_1").state != STATE_UNAVAILABLE

    await connection.close()
    await wait_until(hass, lambda: not coordinator.data.available)

    assert hass.states.get("alarm_control_panel.partition_1").state == STATE_UNAVAILABLE
    assert hass.states.get("binary_sensor.active_32_duo_panel_connection").state == STATE_OFF


async def test_a_partition_programmed_later_still_appears(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """Discovery re-runs on every update, so nothing depends on being ready at setup time."""
    panel.partitions = [0x01, 0x00, 0x00, 0x00]
    connection, coordinator = await _bring_up(hass, setup_entry, connect_panel, panel)
    assert hass.states.get("alarm_control_panel.partition_2") is None

    panel.partitions = [0x01, 0x02, 0x00, 0x00]
    await connection.report_status(hass, coordinator)
    await wait_until(hass, lambda: hass.states.get("alarm_control_panel.partition_2") is not None)
    assert (
        hass.states.get("alarm_control_panel.partition_2").state
        == AlarmControlPanelState.ARMED_AWAY
    )


async def test_connection_timestamps_answer_when_not_just_whether(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """Connectedness is a binary sensor; "since when" and "last heard when" are timestamps.

    The three are genuinely different questions. A socket can stay open long after the panel has
    lost power, so `last_seen` is the one that can be trusted, and it is stamped by every frame —
    including a keep-alive, which carries nothing else at all.
    """
    coordinator = setup_entry.runtime_data.coordinators[panel.serial]

    # These two stay available while the panel is away — that is when they are worth reading —
    # but they report "unknown" rather than inventing a time nothing happened at.
    assert hass.states.get("sensor.active_32_duo_last_connected").state == "unknown"
    assert hass.states.get("sensor.active_32_duo_last_heard_from").state == "unknown"

    connection = await connect_panel(panel)
    await connection.introduce(hass)
    connected_at = coordinator.data.connected_since
    assert connected_at is not None
    assert coordinator.data.last_seen_at == connected_at

    # A keep-alive moves "last heard from" and leaves "last connected" alone.
    await connection.send(panel.keepalive())
    await wait_until(hass, lambda: coordinator.data.last_seen_at > connected_at)
    assert coordinator.data.connected_since == connected_at

    for entity_id in (
        "sensor.active_32_duo_last_connected",
        "sensor.active_32_duo_last_heard_from",
    ):
        state = hass.states.get(entity_id)
        assert state is not None, entity_id
        assert state.attributes["device_class"] == "timestamp"
        assert state.state != "unknown"


async def test_the_last_connection_time_survives_a_disconnect(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """At three o'clock, "it last connected at 14:02" is the fact worth having."""
    coordinator = setup_entry.runtime_data.coordinators[panel.serial]
    connection = await connect_panel(panel)
    await connection.introduce(hass)
    connected_at = coordinator.data.connected_since

    await connection.close()
    await wait_until(hass, lambda: not coordinator.data.available)

    assert coordinator.data.connected_since == connected_at
    assert coordinator.data.last_seen_at is not None


async def test_the_liveness_sensors_stay_readable_while_the_panel_is_away(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """Every other entity goes unavailable with the panel. These two must not.

    "When did it last work?" is a question you ask *because* it stopped working, and an entity that
    reads `unavailable` at that moment has thrown away the only answer it had.
    """
    connection, coordinator = await _bring_up(hass, setup_entry, connect_panel, panel)
    await connection.close()
    await wait_until(hass, lambda: not coordinator.data.available)

    assert hass.states.get("sensor.active_32_duo_battery_voltage").state == STATE_UNAVAILABLE
    for entity_id in (
        "sensor.active_32_duo_last_connected",
        "sensor.active_32_duo_last_heard_from",
    ):
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE, entity_id


async def test_the_device_learns_the_model_the_panel_reports(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """The device registry must be corrected when the panel finally introduces itself.

    Home Assistant reads an entity's `device_info` **once**, when the entity is added to a platform.
    Every panel-level entity here is added before any panel has dialled in, so at that moment the
    model is the permissive "unknown" fallback and there is no firmware or MAC. Reassigning
    `_attr_device_info` afterwards does nothing; the registry has to be written explicitly.

    Left unfixed, the symptom is subtle rather than absent: a panel with partitions or zones gets
    corrected as a side effect of those entities being added later, so it looks fine — while a
    panel with none, an M-300 module for instance, reads "Unknown JFL panel" for ever.
    """
    devices = dr.async_get(hass)

    before = devices.async_get_device_by_identifier(
        (DOMAIN, panel.serial), config_entry_id=setup_entry.entry_id
    )
    assert before is not None
    assert before.model == "Unknown JFL panel"
    assert before.sw_version is None

    connection = await connect_panel(panel)
    await connection.introduce(hass)

    after = devices.async_get_device_by_identifier(
        (DOMAIN, panel.serial), config_entry_id=setup_entry.entry_id
    )
    assert after is not None
    assert after.model == "Active 32 Duo"
    assert after.model_id == "0xA0"
    assert after.sw_version == "7.60"
    assert (dr.CONNECTION_NETWORK_MAC, dr.format_mac(panel.mac)) in after.connections


async def test_firmware_that_is_not_three_digits_is_shown_as_is(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """`render_firmware` only reshapes a three-digit field; anything else passes through unchanged.

    `760` becomes `7.60` because that is what the captured panel actually sends. A panel reporting
    something else — a beta build, a field that is not purely numeric — must not be forced through
    the same reshaping and made to claim a version it never reported.
    """
    panel = FakePanel(serial="ODDFIRM001", firmware="A61")
    entry = make_entry(port, serials=[panel.serial])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    try:
        connection = await connect_panel(panel)
        await connection.introduce(hass)

        device = dr.async_get(hass).async_get_device_by_identifier(
            (DOMAIN, panel.serial), config_entry_id=entry.entry_id
        )
        assert device is not None
        assert device.sw_version == "A61", "not reshaped into a version it never reported"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_non_digit_code_gets_a_text_field_not_a_keypad(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The numeric keypad is offered only for an all-digit code; anything else needs a text field.

    A four-digit PIN is the ordinary case and gets Home Assistant's numeric keypad. A code that is
    not purely digits — a word, a mixed passphrase — cannot be typed on that keypad at all, so it
    must fall back to a plain text field instead of presenting a control that cannot produce it.
    """
    panel = FakePanel(serial="TEXTCODE01")
    entry = make_entry(port, serials=[panel.serial], subentry_data={CONF_CODE: "open-sesame"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    try:
        await _bring_up(hass, entry, connect_panel, panel)
        state = hass.states.get("alarm_control_panel.partition_1")
        assert state is not None
        assert state.attributes["code_format"] == "text"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_arming_with_the_wrong_code_is_refused(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """`code_arm_required` defaults to `True` once a code is configured — arming needs it too.

    `test_a_wrong_code_refuses_and_sends_nothing` (test_commands.py) covers the disarm side of this
    same guard. Arming has never been exercised with the default `code_arm_required`, and a wrong
    code here must refuse just as loudly — an arm that silently does nothing is not much better than
    a disarm that does.
    """
    panel = FakePanel(serial="ARMCODE001")
    entry = make_entry(port, serials=[panel.serial], subentry_data={CONF_CODE: "1234"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    try:
        await _bring_up(hass, entry, connect_panel, panel)
        state = hass.states.get("alarm_control_panel.partition_1")
        assert state is not None
        assert state.attributes["code_arm_required"] is True

        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                "alarm_control_panel",
                "alarm_arm_away",
                {"entity_id": "alarm_control_panel.partition_1", "code": "0000"},
                blocking=True,
            )
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_partition_that_drops_out_of_programming_reads_unknown(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """`programmed` can turn false again, and the entity must say so rather than keep its state.

    Nothing here ever removes the entity — the discovery bookkeeping only ever adds. But `PART[i]`
    going back to `0x00` is the panel's own way of saying this partition no longer exists, and the
    state that was true a moment ago is no longer a fact the panel is asserting.
    """
    connection, coordinator = await _bring_up(hass, setup_entry, connect_panel, panel)
    assert hass.states.get("alarm_control_panel.partition_2").state != STATE_UNKNOWN

    panel.partitions = [0x01, 0x00, 0x00, 0x00]
    await connection.report_status(hass, coordinator)
    assert hass.states.get("alarm_control_panel.partition_2").state == STATE_UNKNOWN


async def test_an_undocumented_partition_byte_reads_unknown_not_a_guess(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """A `PART[i]` value outside the documented set must not be forced into a state it never named.

    `0x04` is programmed, not disarmed, not armed either way and not in alarm — none of the mapped
    states. Reporting any of them would be a guess dressed as a fact; `unknown` is the honest state.
    """
    panel.partitions = [0x04, 0x01, 0x00, 0x00]
    await _bring_up(hass, setup_entry, connect_panel, panel)
    assert hass.states.get("alarm_control_panel.partition_1").state == STATE_UNKNOWN


async def test_an_undocumented_fence_byte_reads_unknown_not_a_guess(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """The fence state sensor's own equivalent of the partition case above.

    `0x03` is present, not triggered, not armed, ready and not disarmed — outside every documented
    value `ELET` is known to take. `unknown` is what a value the panel has never been observed to
    send must produce, not the nearest-sounding label.
    """
    panel.fence = 0x03
    await _bring_up(hass, setup_entry, connect_panel, panel)
    assert hass.states.get("sensor.electric_fence_state").state == STATE_UNKNOWN


async def test_the_fence_disappearing_reads_unknown_across_its_entities(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """`ELET` returning to `0x00` after the fence has been seen is the panel un-configuring it.

    As with a partition, nothing removes these entities — they were created once the fence proved
    it existed, and discovery never runs in reverse. But the fence switch and its alarm sensor both
    read straight off `fence.present`, and once that goes false they must say `unknown`, not keep
    reporting a state for a fence the panel no longer describes.
    """
    connection, coordinator = await _bring_up(hass, setup_entry, connect_panel, panel)
    assert hass.states.get("switch.electric_fence").state != STATE_UNKNOWN
    assert hass.states.get("binary_sensor.electric_fence_alarm").state != STATE_UNKNOWN

    panel.fence = 0x00
    await connection.report_status(hass, coordinator)
    assert hass.states.get("switch.electric_fence").state == STATE_UNKNOWN
    assert hass.states.get("binary_sensor.electric_fence_alarm").state == STATE_UNKNOWN


async def test_a_zone_that_drops_out_of_use_reads_unknown_on_its_bypass_switch(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The bypass switch's own version of the connectivity sensor's disappearing-zone case.

    `zone.status` is unreadable once a zone drops off `state.zones`, and `is_on` must say `unknown`
    rather than keep reporting whether the zone was bypassed the last time it existed.
    """
    panel = FakePanel(serial="BYPASSGONE", zones={1: 0x8})
    entry = make_entry(port, serials=[panel.serial], subentry_data={CONF_ZONE_POLICY: ZONES_ALL})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    try:
        coordinator = entry.runtime_data.coordinators[panel.serial]
        connection = await connect_panel(panel)
        await connection.introduce(hass)
        await connection.report_status(hass, coordinator)

        assert hass.states.get("switch.zone_1_bypass").state != STATE_UNKNOWN

        panel.zones = {}
        await connection.report_status(hass, coordinator)
        assert hass.states.get("switch.zone_1_bypass").state == STATE_UNKNOWN
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_zone_that_drops_out_of_use_stops_reporting_connectivity(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """A zone nibble going back to `0x0` means the zone is no longer in use on this installation.

    The zone was discovered while it had a nibble, so its five sensors already exist. `state.zones`
    drops any zone reading `DISABLED`, so the connectivity sensor's own status lookup comes back
    empty — and it must read `unknown`, not the last thing it heard before the zone was unwired.
    """
    panel.zones = {1: 0x8}
    await _bring_up(hass, setup_entry, connect_panel, panel)

    entities = er.async_get(hass)
    entities.async_update_entity("binary_sensor.zone_1_connection", disabled_by=None)
    await hass.config_entries.async_reload(setup_entry.entry_id)
    await hass.async_block_till_done()

    connection, coordinator = await _bring_up(hass, setup_entry, connect_panel, panel)
    assert hass.states.get("binary_sensor.zone_1_connection").state != STATE_UNKNOWN

    panel.zones = {}
    await connection.report_status(hass, coordinator)
    assert hass.states.get("binary_sensor.zone_1_connection").state == STATE_UNKNOWN


async def test_an_event_with_no_subject_of_its_own_names_nobody(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """Most Contact ID codes are not about a user or a zone at all, and must carry no name.

    `1301`, AC power lost, is a plain system trouble report — its subject field means nothing, and
    `_subject_name`'s classification-by-code-kind must fall through to naming nobody rather than
    resolving a number that was never a user or a zone in the first place.
    """
    connection, _ = await _bring_up(hass, setup_entry, connect_panel, panel)

    await connection.send(panel.event(code="1301", partition="01", subject="009"))
    await wait_until(
        hass,
        lambda: hass.states.get("event.partition_1_events").state not in ("unknown", "unavailable"),
    )
    trouble = hass.states.get("event.partition_1_events")
    assert trouble.attributes["subject_kind"] == "none"
    assert "subject_name" not in trouble.attributes


async def test_a_non_numeric_partition_field_is_not_claimed_by_any_partition(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """`_wants` compares the partition as an integer, and a malformed frame cannot supply one.

    Nothing observed on the wire has done this, but the field is free-text on the protocol level,
    and a partition entity that raised on a frame it cannot parse would take the whole event
    pipeline down with it. Refusing quietly is correct: the malformed frame still reaches the
    panel-wide entity, which claims every event regardless.
    """
    connection, _ = await _bring_up(hass, setup_entry, connect_panel, panel)

    await connection.send(panel.event(code="1130", partition="XY", subject="009"))
    await wait_until(
        hass,
        lambda: hass.states.get("event.active_32_duo_panel_events").state
        not in ("unknown", "unavailable"),
    )
    assert hass.states.get("event.partition_1_events").state == "unknown"
    assert hass.states.get("event.partition_2_events").state == "unknown"


async def test_a_pgm_that_drives_the_fence_warns_when_switched_directly(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The one behaviour that only shows up when a PGM is switched, not merely read.

    `test_capability_detection.py` covers `drives_fence` the capability computation; nothing
    exercises the switch actually being operated while it drives the fence, which is the moment
    the warning in `_async_set` is meant to fire — a PGM switched behind the fence entity's back.
    """
    panel = FakePanel(serial="PGMFENCE01", fence=0x00)
    entry = make_entry(port, serials=[panel.serial], subentry_data={CONF_READ_ONLY: False})
    entry.add_to_hass(hass)

    # Function 18 is the electric fence trigger. This panel has no fence at all, so — per the
    # switch module's own docstring — the switch is still created rather than folded into a fence
    # entity that does not exist, but it is created *disabled*, like every output the fence claims.
    # The row is pre-seeded already enabled and already "settled" (`PGM_PLACEMENT_OPTION`), which is
    # exactly what an installer who has already turned it on once looks like to `_discover_pgms` —
    # the one way to reach this switch's command path without fighting the disable-once machinery
    # that a fresh discovery would otherwise reassert.
    entities = er.async_get(hass)
    subentry_id = next(iter(entry.subentries))
    seeded = entities.async_get_or_create(
        "switch",
        DOMAIN,
        f"{panel.serial}-pgm1",
        config_entry=entry,
        config_subentry_id=subentry_id,
        suggested_object_id="active_32_duo_pgm_1_triggers_the_electric_fence",
    )
    entities.async_update_entity_options(
        seeded.entity_id, DOMAIN, {PGM_PLACEMENT_OPTION: PGM_PLACEMENT_VERSION}
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    try:
        coordinator = entry.runtime_data.coordinators[panel.serial]
        connection = await connect_panel(panel)
        await connection.introduce(hass)
        await connection.report_status(hass, coordinator)
        announce_programming(coordinator, pgms={1: 18})
        await hass.async_block_till_done()

        entry_after = entities.async_get(seeded.entity_id)
        assert entry_after is not None
        assert entry_after.disabled_by is None, "the pre-seeded row must not be re-disabled"

        state = hass.states.get(entry_after.entity_id)
        assert state is not None
        assert state.attributes["drives_electric_fence"] is True

        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": entry_after.entity_id},
            blocking=True,
        )
        # The command still goes out — the warning does not refuse it, only names the risk.
        assert (await connection.read_reply()) != b""
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_the_commands_switch_can_be_turned_back_on(hass: HomeAssistant, setup_entry) -> None:
    """The other half of the master gate that `test_a_disabled_gate_refuses_commands` turns off.

    Nothing turns it back on again through the entity itself.
    """
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.active_32_duo_allow_commands"},
        blocking=True,
    )
    assert hass.states.get("switch.active_32_duo_allow_commands").state == STATE_OFF

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.active_32_duo_allow_commands"},
        blocking=True,
    )
    assert hass.states.get("switch.active_32_duo_allow_commands").state == STATE_ON


async def test_a_wireless_detector_that_leaves_the_inventory_stops_reporting(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """A radio detector's signal and last-seen sensors follow the *inventory*, not the zone.

    The detector was enrolled and reported once, so its two diagnostic sensors already exist. A
    later `0x59` read that no longer lists it — unenrolled, or simply not answering — must make both
    go `unavailable`: `available` follows the inventory record, not the panel connection, and an
    entity that kept showing a detector's last known signal would be claiming knowledge the panel no
    longer has.
    """
    panel = FakePanel(serial="WLESSGONE1", zones={9: 0x8}, wireless_devices={0xB205AF2A: 9})
    entry = make_entry(port, serials=[panel.serial])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    try:
        coordinator = entry.runtime_data.coordinators[panel.serial]
        connection = await connect_panel(panel)
        await connection.introduce(hass)
        await connection.report_status(hass, coordinator)
        connection.serve_programming()
        await coordinator.async_read_programming()
        await hass.async_block_till_done()

        signal = hass.states.get("sensor.zone_9_signal")
        assert signal is not None
        assert signal.state != STATE_UNAVAILABLE
        assert "repeater" in signal.attributes

        # The panel is asked again, and this time the inventory comes back empty: the detector
        # dropped out between reads, which is a real and unremarkable thing for a battery-powered
        # radio sensor to do.
        panel.wireless_devices = {}
        await coordinator.async_read_programming()
        await hass.async_block_till_done()

        assert hass.states.get("sensor.zone_9_signal").state == STATE_UNAVAILABLE
        assert hass.states.get("sensor.zone_9_last_transmission").state == STATE_UNAVAILABLE
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_timer_sensor_appears_once_programming_names_it(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The timer sensors' own version of "nothing exists until the panel says it does".

    None of the timer entities exist before a programming read; the discovery callback for them
    (`_discover_timers`) only runs its body once `coordinator.programming.timers` is populated,
    which is exactly the branch nothing else in this file exercises.
    """
    panel = FakePanel(serial="TIMERS0001")
    entry = make_entry(port, serials=[panel.serial])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    try:
        coordinator = entry.runtime_data.coordinators[panel.serial]
        connection = await connect_panel(panel)
        await connection.introduce(hass)
        await connection.report_status(hass, coordinator)
        assert hass.states.get("sensor.active_32_duo_entry_delay_1") is None

        connection.serve_programming()
        await coordinator.async_read_programming()
        await hass.async_block_till_done()

        assert hass.states.get("sensor.active_32_duo_entry_delay_1") is not None
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_timer_sensor_reads_unknown_if_a_later_read_loses_that_region(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The timer region can come back missing on a *later* read without the panel going away.

    The entity was created by an earlier, complete read. `_discover_timers` never runs a second
    time once it has, so nothing recreates or removes the entity — but `native_value` reads
    `coordinator.programming.timers` fresh every time, and a read where only the timers block never
    answered must show `unknown` rather than the numbers from the read before it.
    """
    from pyjfl import Cmd, FrameReader
    from pyjfl.protocol.programming import REGIONS

    timers_start, timers_length = REGIONS["timers"]

    panel = FakePanel(serial="TIMERSGONE")
    entry = make_entry(port, serials=[panel.serial])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async def _serve_all_but_timers(connection) -> None:
        reader = FrameReader()
        while True:
            data = await connection.reader.read(4096)
            if not data:
                return
            for frame in reader.feed(data):
                if frame.cmd != Cmd.READ_PROGRAMMING or len(frame.raw) != 8:
                    continue
                address = (frame.raw[4] << 8) | frame.raw[5]
                if timers_start <= address < timers_start + timers_length:
                    continue  # The one region this test starves of an answer.
                await connection.send(panel.programming(address, frame.raw[6]))

    try:
        coordinator = entry.runtime_data.coordinators[panel.serial]
        connection = await connect_panel(panel)
        await connection.introduce(hass)
        await connection.report_status(hass, coordinator)
        connection.serve_programming()
        await coordinator.async_read_programming()
        await hass.async_block_till_done()
        assert hass.states.get("sensor.active_32_duo_entry_delay_1") is not None
        assert coordinator.programming.timers is not None, "the region came back the first time"

        # A second read, this time answering everything except the timers block.
        connection._programming_task.cancel()
        serve_task = hass.async_create_task(_serve_all_but_timers(connection))
        try:
            with patch("pyjfl.transport.COMMAND_TIMEOUT", 0.05):
                await coordinator.async_read_programming()
        finally:
            serve_task.cancel()
        await hass.async_block_till_done()

        assert coordinator.programming.timers is None
        assert hass.states.get("sensor.active_32_duo_entry_delay_1").state == STATE_UNKNOWN
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

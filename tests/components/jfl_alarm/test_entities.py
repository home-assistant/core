"""The entities a panel produces once it dials in.

The theme running through these tests is that **nothing exists until the panel says it does**. A
partition that is not programmed produces no entity, and one programmed later still appears without
a reload.
"""

from __future__ import annotations

import pytest

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.components.jfl_alarm.const import DOMAIN
from homeassistant.components.jfl_alarm.device import get_sub_device
from homeassistant.const import CONF_CODE, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import make_entry, wait_until
from .panel_sim import FakePanel


async def _bring_up(hass: HomeAssistant, entry, connect_panel, panel: FakePanel):
    """Connect *panel* and wait until its first status frame has been absorbed."""
    coordinator = entry.runtime_data.coordinators[panel.serial]
    connection = await connect_panel(panel)
    await connection.introduce(hass)
    await connection.report_status(hass, coordinator)
    return connection, coordinator


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
    hass: HomeAssistant,
    setup_entry,
    connect_panel,
    panel: FakePanel,
    raw: int,
    expected: str,
) -> None:
    """The whole `PART[i]` byte, mapped to the alarm panel domain."""
    panel.partitions = [raw, 0x00, 0x00, 0x00]
    await _bring_up(hass, setup_entry, connect_panel, panel)

    state = hass.states.get("alarm_control_panel.partition_1")
    assert state is not None
    assert state.state == expected


async def test_identity_is_on_the_device_and_not_in_entities(
    hass: HomeAssistant,
    setup_entry,
    connect_panel,
    panel: FakePanel,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Model, firmware, serial and MAC belong to the device registry, not to entity attributes."""
    await _bring_up(hass, setup_entry, connect_panel, panel)

    device = device_registry.async_get_device_by_identifier(
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
    keys = {
        entry.unique_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, setup_entry.entry_id
        )
    }
    assert not any(
        "firmware" in key or "model" in key or "serial" in key for key in keys
    )


async def test_partitions_are_sub_devices_of_the_panel(
    hass: HomeAssistant,
    setup_entry,
    connect_panel,
    panel: FakePanel,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The sub-device link is what makes the device page readable on a multi-partition install."""
    await _bring_up(hass, setup_entry, connect_panel, panel)

    panel_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, panel.serial), config_entry_id=setup_entry.entry_id
    )
    sub = get_sub_device(
        hass, setup_entry.entry_id, (DOMAIN, f"{panel.serial}-partition1")
    )
    assert sub is not None
    # `parent_device_id` on 2026.9+ (a child device); `via_device_id` before it — whichever
    # this Home Assistant version has must name the same panel device.
    linked_to = getattr(sub, "parent_device_id", None) or sub.via_device_id
    assert linked_to == panel_device.id


async def test_an_entity_stranded_on_an_enabled_device_is_released(
    hass: HomeAssistant,
    port: int,
    connect_panel,
    panel: FakePanel,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """`disabled_by: device` on a device that is not disabled is a dead end, and setup clears it.

    Home Assistant writes that flag when it disables a device and clears it again when the device is
    re-enabled — but only through the device registry's own update path. A config entry re-enabled
    by editing `.storage` by hand, which is how the lab's was brought back on 2026-08-09, leaves the
    entities stranded: the frontend will not enable one whose device it believes is disabled, and
    the device it names is enabled. The mechanism is generic to any entity on any sub-device; a
    synthetic row on the panel device itself is enough to exercise it here.
    """
    entry = make_entry(port, serials=[panel.serial])
    entry.add_to_hass(hass)
    subentry_id = next(iter(entry.subentries))
    # `async_setup` has not run yet, so the panel device does not exist. Registered by hand here,
    # the same way `__init__.py` registers it before forwarding any platform.
    panel_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=subentry_id,
        identifiers={(DOMAIN, panel.serial)},
    )
    assert not panel_device.disabled, "the device is fine; only the entities are stuck"
    stranded = entity_registry.async_get_or_create(
        "alarm_control_panel",
        DOMAIN,
        f"{panel.serial}-partition1-alarm",
        config_entry=entry,
        config_subentry_id=subentry_id,
        device_id=panel_device.id,
        disabled_by=er.RegistryEntryDisabler.DEVICE,
    )
    assert stranded.disabled_by is er.RegistryEntryDisabler.DEVICE

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    try:
        assert entity_registry.async_get(stranded.entity_id).disabled_by is None
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_an_entity_the_user_disabled_is_left_alone(
    hass: HomeAssistant,
    port: int,
    connect_panel,
    panel: FakePanel,
    entity_registry: er.EntityRegistry,
) -> None:
    """The release is narrow on purpose: only `disabled_by: device`, and only on an enabled device.

    An entity the user switched off themselves is marked `disabled_by: user`, and switching it back
    on behind their back would be worse than the dead end this fixes.
    """
    entry = make_entry(port, serials=[panel.serial])
    entry.add_to_hass(hass)
    chosen = entity_registry.async_get_or_create(
        "alarm_control_panel",
        DOMAIN,
        f"{panel.serial}-partition1-alarm",
        config_entry=entry,
        config_subentry_id=next(iter(entry.subentries)),
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    try:
        assert (
            entity_registry.async_get(chosen.entity_id).disabled_by
            is er.RegistryEntryDisabler.USER
        )
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_an_entity_on_a_still_disabled_device_is_left_alone(
    hass: HomeAssistant,
    port: int,
    connect_panel,
    panel: FakePanel,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """The release only fixes the dead end — a device the user has genuinely disabled is untouched.

    `disabled_by: device` on an entity whose device really is disabled is not a bug to fix: it is
    exactly what Home Assistant itself would have set, and the entity should stay disabled until
    the device is re-enabled through the ordinary path.
    """
    entry = make_entry(port, serials=[panel.serial])
    entry.add_to_hass(hass)
    subentry_id = next(iter(entry.subentries))
    panel_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=subentry_id,
        identifiers={(DOMAIN, panel.serial)},
    )
    device_registry.async_update_device(
        panel_device.id, disabled_by=dr.DeviceEntryDisabler.USER
    )

    stranded = entity_registry.async_get_or_create(
        "alarm_control_panel",
        DOMAIN,
        f"{panel.serial}-partition1-alarm",
        config_entry=entry,
        config_subentry_id=subentry_id,
        device_id=panel_device.id,
        disabled_by=er.RegistryEntryDisabler.DEVICE,
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    try:
        assert (
            entity_registry.async_get(stranded.entity_id).disabled_by
            is er.RegistryEntryDisabler.DEVICE
        )
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_the_last_event_sensor_records_when_not_what(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """The event itself travels on the dispatcher; only its timestamp is coordinator state."""
    connection, coordinator = await _bring_up(hass, setup_entry, connect_panel, panel)
    assert coordinator.data.last_event_at is None

    await connection.send(panel.event())
    await wait_until(hass, lambda: coordinator.data.last_event_at is not None)
    assert coordinator.data.last_event_code == "1130"


async def test_entities_become_unavailable_when_the_panel_goes_away(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """Availability follows the connection, not the coordinator's update history."""
    connection, coordinator = await _bring_up(hass, setup_entry, connect_panel, panel)
    assert hass.states.get("alarm_control_panel.partition_1").state != STATE_UNAVAILABLE

    await connection.close()
    await wait_until(hass, lambda: not coordinator.data.available)

    assert hass.states.get("alarm_control_panel.partition_1").state == STATE_UNAVAILABLE


async def test_a_partition_programmed_later_still_appears(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """Discovery re-runs on every update, so nothing depends on being ready at setup time."""
    panel.partitions = [0x01, 0x00, 0x00, 0x00]
    connection, coordinator = await _bring_up(hass, setup_entry, connect_panel, panel)
    assert hass.states.get("alarm_control_panel.partition_2") is None

    panel.partitions = [0x01, 0x02, 0x00, 0x00]
    await connection.report_status(hass, coordinator)
    await wait_until(
        hass, lambda: hass.states.get("alarm_control_panel.partition_2") is not None
    )
    assert (
        hass.states.get("alarm_control_panel.partition_2").state
        == AlarmControlPanelState.ARMED_AWAY
    )


async def test_the_device_learns_the_model_the_panel_reports(
    hass: HomeAssistant,
    setup_entry,
    connect_panel,
    panel: FakePanel,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The device registry must be corrected when the panel finally introduces itself.

    Home Assistant reads an entity's `device_info` **once**, when the entity is added to a platform.
    Every panel-level entity here is added before any panel has dialled in, so at that moment the
    model is the permissive "unknown" fallback and there is no firmware or MAC. Reassigning
    `_attr_device_info` afterwards does nothing; the registry has to be written explicitly.

    Left unfixed, the symptom is subtle rather than absent: a panel with partitions gets corrected
    as a side effect of those entities being added later, so it looks fine — while a panel with
    none, an M-300 module for instance, reads "Unknown JFL panel" for ever.
    """
    before = device_registry.async_get_device_by_identifier(
        (DOMAIN, panel.serial), config_entry_id=setup_entry.entry_id
    )
    assert before is not None
    assert before.model == "Unknown JFL panel"
    assert before.sw_version is None

    connection = await connect_panel(panel)
    await connection.introduce(hass)

    after = device_registry.async_get_device_by_identifier(
        (DOMAIN, panel.serial), config_entry_id=setup_entry.entry_id
    )
    assert after is not None
    assert after.model == "Active 32 Duo"
    assert after.model_id == "0xA0"
    assert after.sw_version == "7.60"
    assert (dr.CONNECTION_NETWORK_MAC, dr.format_mac(panel.mac)) in after.connections


async def test_firmware_that_is_not_three_digits_is_shown_as_is(
    hass: HomeAssistant, port: int, connect_panel, device_registry: dr.DeviceRegistry
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

        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, panel.serial), config_entry_id=entry.entry_id
        )
        assert device is not None
        assert device.sw_version == "A61", (
            "not reshaped into a version it never reported"
        )
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
    entry = make_entry(
        port, serials=[panel.serial], subentry_data={CONF_CODE: "open-sesame"}
    )
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

"""Arming, disarming and the electric fence — everything this integration sends to a panel.

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

Sprint 3. These tests assert on the **bytes that reach the socket**, not on a mock being called,
because the thing that can go wrong here is sending the wrong command to a real alarm on an occupied
house. Every expected frame below is one that was captured from ActiveNet driving the author's
Active 32 Duo on 2026-08-08, or is the same command with a different partition byte.

The two gates — `read_only` and the commands switch — are tested by asserting that **nothing at
all** was written, which is the only assertion that means anything for a safety interlock.
"""

from __future__ import annotations

import asyncio

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pyjfl import ArmMode, Cmd, FrameReader

from homeassistant.components.jfl_alarm.const import CONF_CODE, CONF_CODE_ARM_REQUIRED, CONF_READ_ONLY
from tests.components.jfl_alarm.conftest import make_entry, wait_until
from tests.components.jfl_alarm.panel_sim import FakePanel

FENCE = 0x63
"""Partition 99, the electric fence."""


async def _bring_up(hass: HomeAssistant, entry, connect_panel, panel: FakePanel):
    """Connect *panel*, absorb one status frame, and drain what the listener wrote back."""
    coordinator = entry.runtime_data.coordinators[panel.serial]
    connection = await connect_panel(panel)
    await connection.introduce(hass)
    await connection.report_status(hass, coordinator)
    return connection, coordinator


async def _writable_entry(hass: HomeAssistant, port: int, panel: FakePanel, **subentry: object):
    """Set up an entry for *panel* with `read_only` off, and unload it afterwards."""
    entry = make_entry(
        port,
        serials=[panel.serial],
        subentry_data={CONF_READ_ONLY: False, **subentry},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _next_command(connection, timeout: float = 2.0):
    """Return the next frame the listener writes that is not a status request.

    A command is followed by two scheduled status re-reads, and on a busy loop one of them can
    overtake the frame under test. Filtering by command byte is what makes these tests describe the
    command rather than the timing.
    """
    reader = FrameReader()
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        data = await connection.read_reply(timeout=timeout)
        for frame in reader.feed(data):
            if frame.cmd != Cmd.STATUS:
                return frame
    raise AssertionError("no command frame arrived")


async def _wrote_nothing(connection, hass: HomeAssistant) -> bool:
    """True if the listener sent no frame at all in the next moment."""
    await hass.async_block_till_done()
    try:
        await connection.read_reply(timeout=0.3)
    except TimeoutError:
        return True
    return False


# --- the fence ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("service", "expected_cmd"),
    [("turn_on", Cmd.ARM), ("turn_off", Cmd.DISARM)],
)
async def test_the_fence_switch_sends_the_captured_frame(
    hass: HomeAssistant, port: int, connect_panel, service: str, expected_cmd: Cmd
) -> None:
    """The project's primary goal, byte for byte.

    Captured from ActiveNet: `7B 06 1A 4E 63 4A` armed the fence and `7B 06 22 4F 63 73` disarmed
    it. Only the sequence byte and therefore the checksum differ here.
    """
    panel = FakePanel(serial="FENCECMD01")
    entry = await _writable_entry(hass, port, panel)
    try:
        connection, _ = await _bring_up(hass, entry, connect_panel, panel)
        await hass.services.async_call(
            "switch", service, {"entity_id": "switch.electric_fence"}, blocking=True
        )
        frame = await _next_command(connection)
        assert frame.cmd == expected_cmd
        assert frame.raw[4] == FENCE
        assert len(frame.raw) == 6
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_the_fence_refuses_when_the_panel_has_not_granted_it(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """`P-ELET` bit 3 clear means the panel would ignore the command. Say which address to check."""
    panel = FakePanel(serial="FENCEDENY1", fence_permissions=0x01)  # may disarm, may not arm
    entry = await _writable_entry(hass, port, panel)
    try:
        connection, _ = await _bring_up(hass, entry, connect_panel, panel)
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                "switch", "turn_on", {"entity_id": "switch.electric_fence"}, blocking=True
            )
        assert await _wrote_nothing(connection, hass)
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


# --- partitions -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("service", "expected_cmd"),
    [
        # The keypad's plain "Armar" — the ordinary full arm.
        ("alarm_arm_away", Cmd.ARM),
        # "Armar STAY" — perimeter only.
        ("alarm_arm_home", Cmd.ARM_STAY),
        ("alarm_disarm", Cmd.DISARM),
        # "Armar AWAY" (`Cmd.ARM_AWAY`, the forced arm) is deliberately absent: it is still a valid
        # protocol command but no longer a Home Assistant arm button — ADR-0016.
    ],
)
async def test_each_arm_mode_sends_its_own_command(
    hass: HomeAssistant, port: int, connect_panel, service: str, expected_cmd: Cmd
) -> None:
    """Each mode sends its own command — and the old integration sent `0x4E` for all of them."""
    panel = FakePanel(serial="ARMMODES01")
    entry = await _writable_entry(hass, port, panel)
    try:
        connection, _ = await _bring_up(hass, entry, connect_panel, panel)
        await hass.services.async_call(
            "alarm_control_panel",
            service,
            {"entity_id": "alarm_control_panel.partition_1"},
            blocking=True,
        )
        frame = await _next_command(connection)
        assert frame.cmd == expected_cmd
        assert frame.raw[4] == 0x01, "partition 1, not the fence and not partition 0"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_all_three_arm_modes_are_offered_on_the_one_entity(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The user asked for the panel's three modes without three different entities."""
    from homeassistant.components.alarm_control_panel import AlarmControlPanelEntityFeature

    panel = FakePanel(serial="FEATURES01")
    entry = await _writable_entry(hass, port, panel)
    try:
        await _bring_up(hass, entry, connect_panel, panel)
        features = hass.states.get("alarm_control_panel.partition_1").attributes[
            "supported_features"
        ]
        assert features & AlarmControlPanelEntityFeature.ARM_AWAY
        assert features & AlarmControlPanelEntityFeature.ARM_HOME
        # Removed 2026-08-09 on the author's decision, after testing all three on the real panel:
        # the forced arm is redundant with the plain arm and reports back identically. ADR-0016.
        assert not features & AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS
        # Never invented: JFL has no night or vacation arming.
        assert not features & AlarmControlPanelEntityFeature.ARM_NIGHT
        assert not features & AlarmControlPanelEntityFeature.ARM_VACATION
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_features_do_not_follow_the_state_dependent_permission_bits(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """`P-PART` read `0x0B` disarmed and `0x1F` armed on the real panel.

    Deriving `supported_features` from it would make Home Assistant's buttons appear and disappear
    on their own, so the features come from the model and the bits are checked at call time.
    """
    from homeassistant.components.alarm_control_panel import AlarmControlPanelEntityFeature

    panel = FakePanel(serial="PARTPERM01", partition_permissions=[0x0B, 0x0B, 0x00, 0x00])
    entry = await _writable_entry(hass, port, panel)
    try:
        connection, _ = await _bring_up(hass, entry, connect_panel, panel)
        features = hass.states.get("alarm_control_panel.partition_1").attributes[
            "supported_features"
        ]
        assert features & AlarmControlPanelEntityFeature.ARM_HOME, "the button still exists"

        # But the call is refused, naming the address to fix rather than failing silently.
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                "alarm_control_panel",
                "alarm_arm_home",
                {"entity_id": "alarm_control_panel.partition_1"},
                blocking=True,
            )
        assert await _wrote_nothing(connection, hass)
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_the_partition_exposes_whether_it_can_be_armed(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """`P-PART` bit 4 is the panel's own "no open zones" — it decides whether a plain arm works."""
    panel = FakePanel(serial="READYBIT01", partition_permissions=[0x0F, 0x1F, 0x00, 0x00])
    entry = await _writable_entry(hass, port, panel)
    try:
        await _bring_up(hass, entry, connect_panel, panel)
        assert hass.states.get("alarm_control_panel.partition_1").attributes["ready"] is False
        assert hass.states.get("alarm_control_panel.partition_2").attributes["ready"] is True
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


# --- the two gates --------------------------------------------------------------------------------


async def test_read_only_mode_sends_nothing_and_says_so(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """The default for a new installation. Silence here would be the worst possible behaviour."""
    connection, _ = await _bring_up(hass, setup_entry, connect_panel, panel)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "alarm_control_panel",
            "alarm_disarm",
            {"entity_id": "alarm_control_panel.partition_1"},
            blocking=True,
        )
    assert await _wrote_nothing(connection, hass)


async def test_the_master_switch_stops_every_command(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """`read_only` is the deliberate opt-in; this is the kill switch on the dashboard."""
    panel = FakePanel(serial="MASTERSW01")
    entry = await _writable_entry(hass, port, panel)
    try:
        connection, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        assert coordinator.commands_enabled is True

        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": "switch.active_32_duo_allow_commands"},
            blocking=True,
        )
        assert coordinator.commands_enabled is False

        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                "switch", "turn_on", {"entity_id": "switch.electric_fence"}, blocking=True
            )
        assert await _wrote_nothing(connection, hass)
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_the_master_switch_stays_available_while_the_panel_is_away(
    hass: HomeAssistant, port: int
) -> None:
    """A setting, not a reading. Switching commands off matters most when the panel misbehaves."""
    panel = FakePanel(serial="MASTERAV01")
    entry = await _writable_entry(hass, port, panel)
    try:
        state = hass.states.get("switch.active_32_duo_allow_commands")
        assert state is not None
        assert state.state == "on"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_command_to_a_disconnected_panel_fails_loudly(
    hass: HomeAssistant, port: int
) -> None:
    """Never a silent no-op: the user pressed disarm and the house is still armed."""
    panel = FakePanel(serial="NOPANEL001")
    entry = await _writable_entry(hass, port, panel)
    try:
        # The alarm entities need a status frame to exist at all, so the fence switch cannot be used
        # here; the coordinator is called directly, which is the same path the entity takes.
        coordinator = entry.runtime_data.coordinators[panel.serial]
        with pytest.raises(HomeAssistantError):
            await coordinator.async_fence(arm=False)
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


# --- the optional Home Assistant code -------------------------------------------------------------


async def test_no_code_is_configured_by_default(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The panel's own keypad already has a code. A second one is opt-in."""
    panel = FakePanel(serial="NOCODE0001")
    entry = await _writable_entry(hass, port, panel)
    try:
        await _bring_up(hass, entry, connect_panel, panel)
        state = hass.states.get("alarm_control_panel.partition_1")
        assert state.attributes["code_format"] is None
        assert state.attributes["code_arm_required"] is False
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_wrong_code_refuses_and_sends_nothing(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """A disarm that quietly does nothing is the worst outcome an alarm integration can have."""
    panel = FakePanel(serial="WITHCODE01")
    entry = await _writable_entry(hass, port, panel, **{CONF_CODE: "4321"})
    try:
        connection, _ = await _bring_up(hass, entry, connect_panel, panel)
        assert hass.states.get("alarm_control_panel.partition_1").attributes["code_format"] == (
            "number"
        )

        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                "alarm_control_panel",
                "alarm_disarm",
                {"entity_id": "alarm_control_panel.partition_1", "code": "0000"},
                blocking=True,
            )
        assert await _wrote_nothing(connection, hass)

        await hass.services.async_call(
            "alarm_control_panel",
            "alarm_disarm",
            {"entity_id": "alarm_control_panel.partition_1", "code": "4321"},
            blocking=True,
        )
        assert (await _next_command(connection)).cmd == Cmd.DISARM
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_the_code_can_be_required_for_disarming_only(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """Leaving is routine; a code typed twenty times a day ends up written on the wall."""
    panel = FakePanel(serial="ARMNOCODE1")
    entry = await _writable_entry(
        hass, port, panel, **{CONF_CODE: "4321", CONF_CODE_ARM_REQUIRED: False}
    )
    try:
        connection, _ = await _bring_up(hass, entry, connect_panel, panel)
        assert (
            hass.states.get("alarm_control_panel.partition_1").attributes["code_arm_required"]
            is False
        )

        await hass.services.async_call(
            "alarm_control_panel",
            "alarm_arm_away",
            {"entity_id": "alarm_control_panel.partition_1"},
            blocking=True,
        )
        assert (await _next_command(connection)).cmd == Cmd.ARM

        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                "alarm_control_panel",
                "alarm_disarm",
                {"entity_id": "alarm_control_panel.partition_1"},
                blocking=True,
            )
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


# --- verification ---------------------------------------------------------------------------------


async def test_a_command_is_followed_by_status_re_reads(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """Nothing is optimistic.

    The status frame that answers a command is not the final truth — arming in the 2026-08-08
    capture returned a frame that still showed zone 9 open, and the panel auto-bypassed it a second
    later. So a command schedules two re-reads and the panel's own answer is what the entities show.
    """
    panel = FakePanel(serial="VERIFY0001")
    entry = await _writable_entry(hass, port, panel)
    try:
        connection, _ = await _bring_up(hass, entry, connect_panel, panel)
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": "switch.electric_fence"}, blocking=True
        )

        seen: list[int] = []
        reader = FrameReader()

        async def _collect() -> None:
            while len(seen) < 3:
                for frame in reader.feed(await connection.read_reply(timeout=5.0)):
                    seen.append(frame.cmd)

        await asyncio.wait_for(_collect(), timeout=8.0)
        assert seen[0] == Cmd.ARM
        assert seen[1:3] == [Cmd.STATUS, Cmd.STATUS], "600 ms and 2 s after the command"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_disconnect_between_command_and_re_read_does_not_raise(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The two scheduled re-reads run unattended, seconds after the call already returned.

    If the panel hangs up in that window, `_verify` has nobody left to report a failure to — the
    calling service call finished already. It has to log and move on rather than raise into
    whatever happens to run the event loop at 600 ms past midnight.
    """
    panel = FakePanel(serial="VERIFYGONE")
    entry = await _writable_entry(hass, port, panel)
    try:
        connection, _ = await _bring_up(hass, entry, connect_panel, panel)
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": "switch.electric_fence"}, blocking=True
        )
        await connection.close()

        # Both VERIFY_DELAYS (0.6 s, 2 s) elapse with nothing to send to. The listener, and the
        # entry, must both still be alive on the other side.
        await asyncio.sleep(2.3)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_the_switch_never_reports_a_state_the_panel_did_not_send(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """Optimistic state on an alarm is a lie with consequences. The switch waits for the panel."""
    panel = FakePanel(serial="NOOPTIMIS1", fence=0x01)
    entry = await _writable_entry(hass, port, panel)
    try:
        connection, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": "switch.electric_fence"}, blocking=True
        )
        await hass.async_block_till_done()
        assert hass.states.get("switch.electric_fence").state == "off", (
            "the panel has not confirmed yet"
        )

        panel.fence = 0x02
        await connection.report_status(hass, coordinator)
        await wait_until(hass, lambda: hass.states.get("switch.electric_fence").state == "on")
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


# --- the lockout guard ----------------------------------------------------------------------------


async def test_one_wrong_password_reply_blocks_and_raises_an_issue(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """AGENTS.md §6: stop on the **first** `0xA1`, not the fifth.

    Nothing this integration sends carries a password, so this reply should be impossible — which is
    exactly why the guard has to exist and be tested rather than assumed.
    """
    from homeassistant.helpers import issue_registry as ir
    from pyjfl import build_frame

    from homeassistant.components.jfl_alarm.const import DOMAIN, ISSUE_REMOTE_ACCESS_BLOCKED

    panel = FakePanel(serial="LOCKOUT001")
    entry = await _writable_entry(hass, port, panel)
    try:
        connection, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        assert coordinator.auth_blocked is False

        # `7B 08 SEQ 37 03 C0 A1 K` — the panel saying "wrong password".
        await connection.send(build_frame(0x40, Cmd.AUTH, bytes([0x03, 0xC0, 0xA1])))
        await wait_until(hass, lambda: coordinator.auth_blocked)

        issues = ir.async_get(hass)
        assert (
            issues.async_get_issue(DOMAIN, f"{ISSUE_REMOTE_ACCESS_BLOCKED}_{panel.serial}")
            is not None
        )
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_an_ordinary_ack_does_not_latch_the_lockout(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """`0xBE` is not one of the two replies that mean remote access is blocked."""
    from pyjfl import build_frame

    panel = FakePanel(serial="ACKOK00001")
    entry = await _writable_entry(hass, port, panel)
    try:
        connection, coordinator = await _bring_up(hass, entry, connect_panel, panel)

        before = coordinator.data.last_seen_at
        await connection.send(build_frame(0x41, Cmd.AUTH, bytes([0x03, 0xC0, 0xBE])))
        # Every packet stamps `last_seen_at`, including this one — the proof the frame was actually
        # received and decoded, which `async_block_till_done` alone does not give: bytes written to
        # a socket do not arrive just because it was called.
        await wait_until(hass, lambda: coordinator.data.last_seen_at != before)
        assert coordinator.auth_blocked is False
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_the_lockout_warning_fires_once_even_across_repeats(
    hass: HomeAssistant, port: int, connect_panel, caplog
) -> None:
    """AGENTS.md §6 says the flag latches on the first `0xA1` and is never cleared automatically.

    A second wrong-password reply after the flag is already set must not warn again or touch the
    repair issue a second time — the flag being `True` is what the early return is for.
    """
    from pyjfl import build_frame

    panel = FakePanel(serial="LOCKOUT002")
    entry = await _writable_entry(hass, port, panel)
    try:
        connection, coordinator = await _bring_up(hass, entry, connect_panel, panel)

        await connection.send(build_frame(0x40, Cmd.AUTH, bytes([0x03, 0xC0, 0xA1])))
        await wait_until(hass, lambda: coordinator.auth_blocked)

        caplog.clear()
        before = coordinator.data.last_seen_at
        await connection.send(build_frame(0x41, Cmd.AUTH, bytes([0x03, 0xC0, 0xA1])))
        await wait_until(hass, lambda: coordinator.data.last_seen_at != before)

        assert coordinator.auth_blocked is True
        assert not any("rejected a command" in record.message for record in caplog.records), (
            "the second wrong password must not warn again"
        )
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


# --- guards without a status frame yet ---------------------------------------------------------


async def test_bypass_before_any_status_frame_refuses_clearly(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """`async_bypass` reads the bypass bitmap from the last status frame — there is none yet.

    Called directly on the coordinator, the same way `_set_bypass_mask` in the service layer does:
    there is no status frame at all here, which the switch platform's own bypass entities cannot
    reach either, since they are not created until a status frame has named which zones exist.
    """
    panel = FakePanel(serial="BYPASSNOS1")
    entry = await _writable_entry(hass, port, panel)
    try:
        connection = await connect_panel(panel)
        await connection.introduce(hass)
        coordinator = entry.runtime_data.coordinators[panel.serial]

        with pytest.raises(HomeAssistantError):
            await coordinator.async_bypass(1, bypassed=True)
        assert await _wrote_nothing(connection, hass)
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_bypassing_a_zone_p_inib_forbids_refuses_and_names_the_address(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """`P-INIB` clear for a zone means the panel would silently ignore `0x52` for it.

    Unlike the switch platform — which does not create a bypass entity for a zone `P-INIB`
    forbids, so a user can never press a button that would do this — `async_bypass` is also the
    function `set_bypass_mask` calls, and that service takes any zone number at all.
    """
    panel = FakePanel(serial="BYPASSDENY", bypassable=bytes(13), zones={1: 0x8})
    entry = await _writable_entry(hass, port, panel)
    try:
        connection, coordinator = await _bring_up(hass, entry, connect_panel, panel)

        with pytest.raises(ServiceValidationError):
            await coordinator.async_bypass(1, bypassed=True)
        assert await _wrote_nothing(connection, hass)
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_pgm_before_any_status_frame_is_permitted_by_default(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """`_require_pgm_permission` has nothing to check against yet, so it must not refuse.

    Refusing here on our own guess would block a command the panel would have accepted — the same
    reasoning the permissive partition and fence defaults use. The PGM switches themselves wait for
    `pgm_functions_known`, so this calls the coordinator directly, the way the switch platform does.
    """
    panel = FakePanel(serial="PGMNOSTAT1")
    entry = await _writable_entry(hass, port, panel)
    try:
        connection = await connect_panel(panel)
        await connection.introduce(hass)
        coordinator = entry.runtime_data.coordinators[panel.serial]

        await coordinator.async_pgm(1, on=True)
        frame = await _next_command(connection)
        assert frame.cmd == Cmd.PGM_ON
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_arming_before_any_status_frame_is_permitted_by_default(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """`_partition_permissions` has nothing to check against yet, so arming must not be refused.

    The panel is the authority on `P-PART`; refusing on our own guess before its first status frame
    would block a command the panel would have accepted. Called directly on the coordinator, the
    same way the PGM and bypass equivalents above are: `alarm_control_panel.partition_1` itself is
    discovered from `state.partitions`, so there is no such entity yet to call a service on before
    a status frame has ever arrived.
    """
    panel = FakePanel(serial="ARMNOSTAT1")
    entry = await _writable_entry(hass, port, panel)
    try:
        connection = await connect_panel(panel)
        await connection.introduce(hass)
        coordinator = entry.runtime_data.coordinators[panel.serial]

        await coordinator.async_arm(1, ArmMode.TOTAL)
        frame = await _next_command(connection)
        assert frame.cmd == Cmd.ARM
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

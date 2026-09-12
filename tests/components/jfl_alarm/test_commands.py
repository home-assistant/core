"""Arming and disarming — everything this integration sends to a panel in this PR.

These tests assert on the bytes that reach the socket rather than on a mock being called, because
what can go wrong here is sending the wrong command to a real alarm on an occupied house. Every
expected frame below was captured from the manufacturer's own software driving an Active 32 Duo, or
is the same command with a different partition byte.

`read_only` is tested by asserting that nothing at all was written, which is the only assertion that
means anything for a safety interlock.
"""

from __future__ import annotations

import asyncio

from pyjfl import ArmMode, Cmd, FrameReader, build_frame
import pytest

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntityFeature
from homeassistant.components.jfl_alarm.const import (
    CONF_CODE_ARM_REQUIRED,
    CONF_READ_ONLY,
)
from homeassistant.const import CONF_CODE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import make_entry, wait_until
from .panel_sim import FakePanel


async def _bring_up(hass: HomeAssistant, entry, connect_panel, panel: FakePanel):
    """Connect *panel*, absorb one status frame, and drain what the listener wrote back."""
    coordinator = entry.runtime_data.coordinators[panel.serial]
    connection = await connect_panel(panel)
    await connection.introduce(hass)
    await connection.report_status(hass, coordinator)
    return connection, coordinator


async def _writable_entry(
    hass: HomeAssistant, port: int, panel: FakePanel, **subentry: object
):
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
        # protocol command but is not offered as a Home Assistant arm button.
    ],
)
async def test_each_arm_mode_sends_its_own_command(
    hass: HomeAssistant, port: int, connect_panel, service: str, expected_cmd: Cmd
) -> None:
    """Each mode sends its own command, rather than `0x4E` standing in for all of them."""
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
    """Both arm modes live on one entity rather than on two."""
    panel = FakePanel(serial="FEATURES01")
    entry = await _writable_entry(hass, port, panel)
    try:
        await _bring_up(hass, entry, connect_panel, panel)
        features = hass.states.get("alarm_control_panel.partition_1").attributes[
            "supported_features"
        ]
        assert features & AlarmControlPanelEntityFeature.ARM_AWAY
        assert features & AlarmControlPanelEntityFeature.ARM_HOME
        # Not offered: the forced arm is redundant with the plain arm from a user's point of view,
        # and the panel reports both identically afterwards.
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
    panel = FakePanel(
        serial="PARTPERM01", partition_permissions=[0x0B, 0x0B, 0x00, 0x00]
    )
    entry = await _writable_entry(hass, port, panel)
    try:
        connection, _ = await _bring_up(hass, entry, connect_panel, panel)
        features = hass.states.get("alarm_control_panel.partition_1").attributes[
            "supported_features"
        ]
        assert features & AlarmControlPanelEntityFeature.ARM_HOME, (
            "the button still exists"
        )

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


# --- read-only mode --------------------------------------------------------------------------------


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


async def test_a_command_to_a_disconnected_panel_fails_loudly(
    hass: HomeAssistant, port: int
) -> None:
    """Never a silent no-op: the user pressed disarm and the house is still armed."""
    panel = FakePanel(serial="NOPANEL001")
    entry = await _writable_entry(hass, port, panel)
    try:
        # The alarm entities need a status frame to exist at all, so the coordinator is called
        # directly, which is the same path the entity takes.
        coordinator = entry.runtime_data.coordinators[panel.serial]
        with pytest.raises(HomeAssistantError):
            await coordinator.async_disarm(1)
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
        assert hass.states.get("alarm_control_panel.partition_1").attributes[
            "code_format"
        ] == ("number")

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
            hass.states.get("alarm_control_panel.partition_1").attributes[
                "code_arm_required"
            ]
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


# --- the lockout guard ----------------------------------------------------------------------------


async def test_an_ordinary_ack_does_not_latch_the_lockout(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """`0xBE` is not one of the two replies that mean remote access is blocked."""
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
    hass: HomeAssistant, port: int, connect_panel, caplog: pytest.LogCaptureFixture
) -> None:
    """The flag latches on the first `0xA1` and is never cleared automatically.

    A second wrong-password reply after the flag is already set must not warn again or touch the
    repair issue a second time — the flag being `True` is what the early return is for.
    """
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
        assert not any(
            "rejected a command" in record.message for record in caplog.records
        ), "the second wrong password must not warn again"
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


# --- guards without a status frame yet ---------------------------------------------------------


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

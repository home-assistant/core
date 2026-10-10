"""The listener, exercised over real sockets.

Every test here opens an actual TCP connection to an actual `asyncio.start_server`. That is
deliberate: the sprint's acceptance criteria are all about socket behaviour, and a mocked socket
cannot fail a single one of them.
"""

from __future__ import annotations

import asyncio
import socket

from pyjfl import Cmd, FrameReader
import pytest

from homeassistant.components.jfl_alarm.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import LOOPBACK, make_entry, wait_until
from .panel_sim import FakePanel


def _frames(data: bytes) -> list:
    """Parse whatever the listener wrote back."""
    return FrameReader().feed(data)


async def test_connection_frame_is_accepted_and_echoes_the_panel_seq(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """The `0x21` reply must carry `RESULT = 0x01` and the **panel's** sequence byte."""
    connection = await connect_panel(panel)
    sent_seq = panel.seq + 1
    reply = await connection.introduce(hass)

    [frame] = _frames(reply)
    assert frame.cmd == Cmd.CONNECTION
    assert frame.seq == sent_seq
    assert frame.payload[0] == 0x01


async def test_keepalive_is_answered_immediately(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """A keep-alive that goes unanswered makes the panel give up on us."""
    connection = await connect_panel(panel)
    await connection.introduce(hass)

    await connection.send(panel.keepalive())
    [frame] = _frames(await connection.read_reply())
    assert frame.cmd == Cmd.KEEP_ALIVE
    assert 1 <= frame.payload[0] <= 20


async def test_event_is_acknowledged_with_the_counter_echoed(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """The counter is binary and must come back verbatim, or the panel repeats the event."""
    connection = await connect_panel(panel)
    await connection.introduce(hass)

    await connection.send(panel.event(counter=b"\x00\x01\x02\x03"))
    [frame] = _frames(await connection.read_reply())
    assert frame.cmd == Cmd.EVENT
    assert frame.payload == b"\x01\x00\x01\x02\x03"


async def test_event_is_acknowledged_even_when_decoding_fails(
    hass: HomeAssistant,
    setup_entry,
    connect_panel,
    panel: FakePanel,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unacknowledged event is retransmitted for ever, so a decoding bug must not cost the ack.

    This is the single most consequential ordering decision in the read path, so it is tested by
    breaking the decoder outright rather than by hoping a malformed frame happens to break it.
    """
    connection = await connect_panel(panel)
    await connection.introduce(hass)

    def _explode(frame):
        raise ValueError("decoder is broken")

    monkeypatch.setattr("pyjfl.transport.decode", _explode)

    await connection.send(panel.event(counter=b"\x0a\x0b\x0c\x0d"))
    [frame] = _frames(await connection.read_reply())
    assert frame.cmd == Cmd.EVENT
    assert frame.payload == b"\x01\x0a\x0b\x0c\x0d"


async def test_garbage_does_not_kill_the_listener(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """A malformed frame must not take down a listener that is serving other panels."""
    connection = await connect_panel(panel)
    await connection.introduce(hass)

    await connection.send(bytes(range(64)))
    await asyncio.sleep(0)

    # The same socket keeps working, which is the strong form of the claim: the reader
    # resynchronised rather than the connection being torn down and re-established.
    await connection.send(panel.keepalive())
    [frame] = _frames(await connection.read_reply())
    assert frame.cmd == Cmd.KEEP_ALIVE


async def test_a_reconnect_replaces_only_that_panel(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """Killing a panel mid-session and restarting it must recover cleanly."""
    first = await connect_panel(panel)
    await first.introduce(hass)
    runtime = setup_entry.runtime_data
    assert runtime.server.link(panel.serial).connected

    await first.close()
    await hass.async_block_till_done()

    second = await connect_panel(panel)
    reply = await second.introduce(hass)
    assert _frames(reply)[0].payload[0] == 0x01
    assert runtime.server.link(panel.serial).connected

    # And it is usable, not merely marked connected.
    await second.report_status(hass, runtime.coordinators[panel.serial])
    assert runtime.coordinators[panel.serial].data.status is not None


async def test_a_redial_before_the_old_socket_died_keeps_the_panel_available(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """A panel whose old socket has not been noticed yet must not flap to unavailable."""
    first = await connect_panel(panel)
    await first.introduce(hass)

    second = await connect_panel(panel)
    await second.introduce(hass)

    coordinator = setup_entry.runtime_data.coordinators[panel.serial]
    assert coordinator.data.available is True


async def test_three_models_on_one_port_produce_three_independent_devices(
    hass: HomeAssistant, port: int, connect_panel, device_registry: dr.DeviceRegistry
) -> None:
    """The sprint's headline acceptance criterion.

    Three panels of different models, on one listener, must produce three devices with the entity
    set each model implies and no state leaking between them.
    """
    panels = [
        # Active 32 Duo: four partitions, a fence.
        FakePanel(
            serial="AAAAAAAAAA", model_byte=0xA0, partitions=[0x01, 0x02, 0x00, 0x00]
        ),
        # Active 8 Ultra: two partitions, no fence at all.
        FakePanel(
            serial="BBBBBBBBBB", model_byte=0xA2, partitions=[0x01, 0x00], fence=0x00
        ),
        # Active 100 Bus: sixteen partitions.
        FakePanel(
            serial="CCCCCCCCCC", model_byte=0xA4, partitions=[0x03] * 3, fence=0x02
        ),
    ]
    entry = make_entry(port, serials=[panel.serial for panel in panels])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    try:
        coordinators = entry.runtime_data.coordinators
        for panel in panels:
            connection = await connect_panel(panel)
            await connection.introduce(hass)
            await connection.report_status(hass, coordinators[panel.serial])

        assert set(coordinators) == {panel.serial for panel in panels}

        # State did not leak: each coordinator holds its own panel's model and partitions.
        assert coordinators["AAAAAAAAAA"].data.spec.name == "Active 32 Duo"
        assert coordinators["BBBBBBBBBB"].data.spec.name == "Active 8 Ultra"
        assert coordinators["CCCCCCCCCC"].data.spec.name == "Active 100 Bus"

        # The model caps what is read: the frame always carries sixteen partition bytes.
        assert len(coordinators["AAAAAAAAAA"].data.partitions) == 4
        assert len(coordinators["BBBBBBBBBB"].data.partitions) == 2
        assert len(coordinators["CCCCCCCCCC"].data.partitions) == 16

        for panel in panels:
            assert (
                device_registry.async_get_device_by_identifier(
                    (DOMAIN, panel.serial), config_entry_id=entry.entry_id
                )
                is not None
            )
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_unloading_actually_frees_the_port(
    hass: HomeAssistant, entry, port: int
) -> None:
    """Tested by rebinding the port for real, because that is the only thing that proves it."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with (
        pytest.raises(OSError),
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as taken,
    ):
        taken.bind((LOOPBACK, port))

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as freed:
        freed.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        freed.bind((LOOPBACK, port))


async def test_a_busy_port_leaves_the_entry_retrying(
    hass: HomeAssistant, port: int
) -> None:
    """A bind failure is `ConfigEntryNotReady`: whatever holds the port may well let go."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
        holder.bind((LOOPBACK, port))
        holder.listen(1)

        entry = make_entry(port)
        entry.add_to_hass(hass)
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_an_unknown_panel_is_added_automatically(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The default policy. A panel dials in and becomes a subentry with no user action."""
    entry = make_entry(port, serials=[])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    try:
        panel = FakePanel(serial="NEWPANEL01")
        connection = await connect_panel(panel)
        reply = await connection.introduce(hass)
        assert _frames(reply)[0].payload[0] == 0x01

        await wait_until(
            hass,
            lambda: any(
                sub.unique_id == panel.serial for sub in entry.subentries.values()
            ),
        )
        # Adding the subentry reloads the entry. Let that finish before unloading, or the reload
        # lands afterwards and leaves a second listener holding the port.
        await hass.async_block_till_done()
    finally:
        if entry.state.recoverable:
            await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()


async def test_the_status_poll_asks_the_panel(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """The panel never volunteers its status, so `0x4D` has to go out — read-only or not."""
    connection = await connect_panel(panel)
    await connection.introduce(hass)

    coordinator = setup_entry.runtime_data.coordinators[panel.serial]
    assert coordinator.read_only is True
    await coordinator.async_refresh_status()
    await hass.async_block_till_done()

    [frame] = _frames(await connection.read_reply())
    assert frame.cmd == Cmd.STATUS


async def test_the_raw_frame_ring_buffer_records_both_directions(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """A bug report is worth much more with fifty frames of real traffic attached."""
    connection = await connect_panel(panel)
    await connection.introduce(hass)
    await connection.report_status(
        hass, setup_entry.runtime_data.coordinators[panel.serial]
    )

    frames = setup_entry.runtime_data.server.link(panel.serial).frames
    assert any(frame.outbound for frame in frames)
    assert any(not frame.outbound for frame in frames)

"""The service layer: `sync_time`, `refresh_status` and `set_bypass_mask`.

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

Sprint 4. These services target the panel or a coordinator method directly through a device id, and
are not tied to any entity platform — they stay registered regardless of which platforms this build
ships. `test_read_only_mode_stops_the_services_too` is the one that matters: a gate that only guards
the entities is not a gate.
"""

from __future__ import annotations

import asyncio

from pyjfl import Cmd, FrameReader, bitmap_to_flags
import pytest

from homeassistant.components.jfl_alarm.const import CONF_READ_ONLY, DOMAIN
from homeassistant.components.jfl_alarm.device import get_sub_device
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import make_entry
from .panel_sim import FakePanel


async def _bring_up(hass: HomeAssistant, entry, connect_panel, panel: FakePanel):
    """Connect *panel* and absorb one status frame."""
    coordinator = entry.runtime_data.coordinators[panel.serial]
    connection = await connect_panel(panel)
    await connection.introduce(hass)
    await connection.report_status(hass, coordinator)
    return connection, coordinator


async def _writable_entry(
    hass: HomeAssistant, port: int, panel: FakePanel, **subentry: object
):
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


def _panel_device_id(
    device_registry: dr.DeviceRegistry, entry_id: str, serial: str
) -> str:
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, serial), config_entry_id=entry_id
    )
    assert device is not None
    return device.id


# --- services ---------------------------------------------------------------------------------


async def test_the_services_are_registered_without_any_entry(
    hass: HomeAssistant,
) -> None:
    """Registered in `async_setup`, so an automation validates while the entry is unloaded."""
    assert await async_setup_component(hass, DOMAIN, {})
    for service in ("sync_time", "refresh_status", "set_bypass_mask"):
        assert hass.services.has_service(DOMAIN, service)


async def test_sync_time_sends_the_clock_in_the_panels_own_order(
    hass: HomeAssistant,
    port: int,
    connect_panel,
    device_registry: dr.DeviceRegistry,
) -> None:
    """`0x55` is **hour first**, which is the reverse of the clock the status frame reports."""
    panel = FakePanel(serial="SYNCTIME01")
    entry = await _writable_entry(hass, port, panel)
    try:
        connection, _ = await _bring_up(hass, entry, connect_panel, panel)
        await hass.services.async_call(
            DOMAIN,
            "sync_time",
            {
                "device_id": _panel_device_id(
                    device_registry, entry.entry_id, panel.serial
                )
            },
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
    hass: HomeAssistant,
    setup_entry,
    connect_panel,
    panel: FakePanel,
    device_registry: dr.DeviceRegistry,
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
        {
            "device_id": _panel_device_id(
                device_registry, setup_entry.entry_id, panel.serial
            )
        },
        blocking=True,
    )
    reply = await connection.read_reply()
    assert FrameReader().feed(reply)[0].cmd == Cmd.STATUS


async def test_set_bypass_mask_replaces_the_whole_list(
    hass: HomeAssistant,
    port: int,
    connect_panel,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Including with an empty list, which is how every bypass is cleared."""
    panel = FakePanel(serial="MASKSVC001", zones={1: 0x1, 9: 0x1})
    entry = await _writable_entry(hass, port, panel)
    try:
        connection, _ = await _bring_up(hass, entry, connect_panel, panel)
        device_id = _panel_device_id(device_registry, entry.entry_id, panel.serial)

        await hass.services.async_call(
            DOMAIN,
            "set_bypass_mask",
            {"device_id": device_id, "zones": [3, 4]},
            blocking=True,
        )
        frame = await _next_command(connection)
        assert bitmap_to_flags(frame.raw[4:17], lsb_first=False) == frozenset({3, 4})

        await hass.services.async_call(
            DOMAIN,
            "set_bypass_mask",
            {"device_id": device_id, "zones": []},
            blocking=True,
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
        partition = get_sub_device(
            hass, entry.entry_id, (DOMAIN, f"{panel.serial}-partition1")
        )
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
    assert await async_setup_component(hass, DOMAIN, {})
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "sync_time", {"device_id": "does-not-exist"}, blocking=True
        )


async def test_read_only_mode_stops_the_services_too(
    hass: HomeAssistant,
    setup_entry,
    connect_panel,
    panel: FakePanel,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A gate that only guards the entities is not a gate."""
    connection, _ = await _bring_up(hass, setup_entry, connect_panel, panel)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "set_bypass_mask",
            {
                "device_id": _panel_device_id(
                    device_registry, setup_entry.entry_id, panel.serial
                ),
                "zones": [1],
            },
            blocking=True,
        )
    with pytest.raises(TimeoutError):
        await connection.read_reply(timeout=0.3)

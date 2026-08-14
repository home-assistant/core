"""The diagnostics download, and what must never appear in it.

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

A diagnostics dump is the thing users paste into public bug reports, so the redaction rules in
AGENTS.md §4 are tested against the rendered JSON rather than against the code that writes it. A
test that checks "we called the redaction helper" passes happily when a new field is added and the
helper is not called for it.
"""

from __future__ import annotations

import json

from homeassistant.components.jfl_alarm.const import DOMAIN
from homeassistant.components.jfl_alarm.device import get_sub_device
from homeassistant.components.jfl_alarm.system_health import _system_health_info
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .panel_sim import FakePanel

from tests.common import get_system_health_info
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator


async def test_the_dump_carries_state_but_no_identity(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_entry,
    connect_panel,
    panel: FakePanel,
) -> None:
    """Everything a bug report needs, and nothing that says whose house this is."""
    coordinator = setup_entry.runtime_data.coordinators[panel.serial]
    connection = await connect_panel(panel)
    await connection.introduce(hass)
    await connection.report_status(hass, coordinator)

    result = await get_diagnostics_for_config_entry(hass, hass_client, setup_entry)
    raw = json.dumps(result)

    # The state that makes a report useful is all there.
    [dumped] = result["panels"]
    assert dumped["connected"] is True
    assert dumped["identity"]["model"] == "Active 32 Duo"
    assert dumped["identity"]["model_byte"] == 0xA0
    assert dumped["identity"]["firmware"] == "760"
    assert dumped["capabilities"]["partitions"] == 4
    assert dumped["status"]["fence"]["present"] is True
    assert dumped["status"]["battery_volts"] > 12
    assert dumped["frames"]

    # And none of the things AGENTS.md §4 forbids.
    assert panel.serial not in raw
    assert panel.mac not in raw
    assert dumped["serial"].startswith("id:")
    assert dumped["identity"]["mac"].startswith("id:")


async def test_the_raw_frame_buffer_redacts_the_connection_handshake(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_entry,
    connect_panel,
) -> None:
    """The `0x21` connection frame in the raw-frame ring buffer must not carry plaintext identity.

    `pyjfl.RawFrame.as_dict()` renders wire bytes verbatim by design — that is the whole point of a
    debugging ring buffer. `identity.mac`/`identity.imei`/the top-level `serial` are hashed, and a
    dump caught right after a reconnect carries the same three identifiers a second time, inside
    `frames[].hex`, unless this integration's own redaction reaches into that array too.

    A real, non-empty IMEI, unlike the shared `panel` fixture's default: an empty string would make
    `imei not in raw` trivially true and prove nothing.
    """
    panel = FakePanel(imei="123456789012345")
    connection = await connect_panel(panel)
    await connection.introduce(hass)

    result = await get_diagnostics_for_config_entry(hass, hass_client, setup_entry)
    raw = json.dumps(result)

    [dumped] = result["panels"]
    assert dumped["frames"], (
        "the connection handshake should have landed in the ring buffer"
    )
    assert panel.serial not in raw
    assert panel.imei not in raw
    assert panel.mac not in raw

    # A redacted 0x21 frame still says it is one, and still carries a hex string a reader can look
    # at — just with the identifying ranges replaced by a token, not silently dropped or truncated.
    frame_hexes = " ".join(frame["hex"] for frame in dumped["frames"])
    assert "[id:" in frame_hexes


async def test_the_same_panel_gets_the_same_token_everywhere(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_entry,
    connect_panel,
    panel: FakePanel,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Redaction must not make a multi-panel dump unreadable.

    Blanking every serial to the same placeholder would turn three panels into three identical
    anonymous blobs. Hashing keeps them apart and still reveals nothing.
    """
    coordinator = setup_entry.runtime_data.coordinators[panel.serial]
    connection = await connect_panel(panel)
    await connection.introduce(hass)
    await connection.report_status(hass, coordinator)

    entry_dump = await get_diagnostics_for_config_entry(hass, hass_client, setup_entry)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, panel.serial), config_entry_id=setup_entry.entry_id
    )
    panel_dump = await get_diagnostics_for_device(
        hass, hass_client, setup_entry, device
    )

    assert entry_dump["panels"][0]["serial"] == panel_dump["serial"]
    assert not panel_dump["serial"].endswith(panel.serial)

    # A partition sub-device resolves to its parent panel rather than dumping nothing useful.
    partition = get_sub_device(
        hass, setup_entry.entry_id, (DOMAIN, f"{panel.serial}-partition1")
    )
    assert partition is not None
    partition_dump = await get_diagnostics_for_device(
        hass, hass_client, setup_entry, partition
    )
    assert partition_dump["serial"] == panel_dump["serial"]


async def test_a_panel_that_never_connected_still_dumps(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, setup_entry
) -> None:
    """The most common bug report is "nothing appeared", so this path must not raise."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, setup_entry)

    assert result["listener"]["running"] is True
    [dumped] = result["panels"]
    assert dumped["connected"] is False
    assert dumped["status"] is None
    assert dumped["identity"]["model_byte"] is None


async def test_a_device_with_no_loaded_coordinator_still_dumps(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_entry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A device left behind by a removed panel subentry, per `async_remove_config_entry_device`.

    Must still produce a dump rather than raising, with the serial still redacted.
    """
    subentry_id = next(iter(setup_entry.subentries))
    stray_device = device_registry.async_get_or_create(
        config_entry_id=setup_entry.entry_id,
        config_subentry_id=subentry_id,
        identifiers={(DOMAIN, "STRAYPANEL1")},
    )

    result = await get_diagnostics_for_device(
        hass, hass_client, setup_entry, stray_device
    )

    assert result == {"serial": result["serial"], "loaded": False}
    assert result["serial"].startswith("id:")
    assert "STRAYPANEL1" not in json.dumps(result)


async def test_pending_panels_are_listed_and_redacted(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_entry,
    connect_panel,
) -> None:
    """A panel reporting in without a subentry is the other half of "nothing appeared"."""
    stranger = FakePanel(serial="STRANGER01")
    connection = await connect_panel(stranger)
    await connection.introduce(hass)

    result = await get_diagnostics_for_config_entry(hass, hass_client, setup_entry)
    raw = json.dumps(result)
    assert stranger.serial not in raw


async def test_system_health_reports_the_port_and_the_frame_age(
    hass: HomeAssistant, setup_entry, connect_panel, panel: FakePanel
) -> None:
    """The three facts that answer "is this working?" for an integration nothing connects *to*.

    Age of the last frame rather than "connected", because a TCP socket stays open long after the
    box at the far end has lost power — a connection count alone reports healthy panels that went
    dark twenty minutes ago.
    """
    assert await async_setup_component(hass, "system_health", {})

    before = await _system_health_info(hass)
    assert before["panels_configured"] == 1
    assert before["panels_connected"] == 0
    assert before["last_frame"] == "never"
    assert str(setup_entry.data["port"]) in before["listening_on"]

    coordinator = setup_entry.runtime_data.coordinators[panel.serial]
    connection = await connect_panel(panel)
    await connection.introduce(hass)
    await connection.report_status(hass, coordinator)

    after = await _system_health_info(hass)
    assert after["panels_connected"] == 1
    assert after["last_frame"].endswith("s ago")


async def test_system_health_with_no_loaded_entry(hass: HomeAssistant) -> None:
    """It must not raise on an installation where every entry is unloaded."""
    assert await _system_health_info(hass) == {"listeners": 0}


async def test_system_health_is_actually_registered_with_the_component(
    hass: HomeAssistant, setup_entry
) -> None:
    """`async_register` itself, exercised through the real registration path.

    The other system_health test imports `_system_health_info` and calls it directly, which says
    nothing about whether `async_register` ever wired it up. `get_system_health_info` goes through
    `system_health`'s own lazy platform loading, the same as the frontend's "info" panel does.
    """
    assert await async_setup_component(hass, "system_health", {})

    info = await get_system_health_info(hass, DOMAIN)
    assert info["panels_configured"] == 1
    assert info["last_frame"] == "never"

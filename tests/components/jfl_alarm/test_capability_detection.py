"""Capability detection through Home Assistant: the fence PGM, and per-model entity sets.

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

Sprint 8, tasks 8.1 and 8.2. The pure merge logic is covered in `tests/test_capabilities.py`; these
tests are about what it *does* in Home Assistant — the repair issues a programming read raises when
a PGM turns out to drive the electric fence, and the promise that a panel with no fence, no PGMs or
no partitions produces exactly the entities for what it has.

The load-bearing one is `test_a_detected_fence_pgm_gets_no_switch`: it is the moment ADR-0007's
residual risk closes, and it is the only test that drives the whole path over a socket — a real
`0x44` read, the function decoded from it, and the entity set decided by that function. A user who
never told the integration which PGM triggers the fence used to get an ordinary-looking switch on
the panel's dashboard and a repair issue asking them to fix it by hand. Now the read settles it, and
the answer for that output is **no entity**: the fence's own switch is how the fence is operated.
ADR-0017.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from homeassistant.components.jfl_alarm.const import CONF_FENCE_PGM, CONF_READ_ONLY, DOMAIN
from tests.components.jfl_alarm.conftest import make_entry
from tests.components.jfl_alarm.panel_sim import FakePanel

# The fence's own PGM: attribute byte 5 = 18. Two ordinary outputs beside it, so detection has to
# pick the right one rather than the first.
FENCE_PGM_PANEL = {
    "pgm_functions": {1: 12, 2: 18, 3: 11},
    "pgm_durations": {2: 0xCA},
    "pgm_names": {2: "Cerca"},
}


async def _entry_for(hass: HomeAssistant, port: int, panel: FakePanel, **subentry: object):
    entry = make_entry(
        port, serials=[panel.serial], subentry_data={CONF_READ_ONLY: True, **subentry}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _bring_up(hass: HomeAssistant, entry, connect_panel, panel: FakePanel):
    """Connect *panel*, absorb one status frame, and let it answer programming reads."""
    coordinator = entry.runtime_data.coordinators[panel.serial]
    connection = await connect_panel(panel)
    await connection.introduce(hass)
    await connection.report_status(hass, coordinator)
    connection.serve_programming()
    return connection, coordinator


# --- 8.2: detecting the fence's PGM, and closing ADR-0007's residual risk ------------------------


async def test_a_detected_fence_pgm_gets_no_switch(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """A read finds the energiser's output and *withholds* its switch, on a panel nobody configured.

    The whole point of 8.2, finished by ADR-0017. Nothing exists before the read, because a PGM's
    function is what decides whether its switch exists. After it, PGM 2 — the energiser's trigger —
    has no entity at all, while PGMs 1 and 3, a user output and a scheduled one, are ordinary
    controls on the panel. **No repair issue is raised**: there is nothing left for the user to do.
    """
    panel = FakePanel(serial="FENCEPGM01", **FENCE_PGM_PANEL)
    entry = await _entry_for(hass, port, panel)  # fence_pgm not set: 0, "none / I don't know"
    try:
        _, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        entities = er.async_get(hass)
        issues = ir.async_get(hass)

        # No switch at all before the read: the function is what decides, and it is unknown.
        assert entities.async_get_entity_id("switch", DOMAIN, f"{panel.serial}-pgm1") is None

        await coordinator.async_read_programming()
        await hass.async_block_till_done()

        assert coordinator.capabilities.detected_fence_pgm == 2
        assert entities.async_get_entity_id("switch", DOMAIN, f"{panel.serial}-pgm2") is None

        panel_device = dr.async_get(hass).async_get_device_by_identifier(
            (DOMAIN, panel.serial), config_entry_id=entry.entry_id
        )
        ordinary = entities.async_get(
            entities.async_get_entity_id("switch", DOMAIN, f"{panel.serial}-pgm1")
        )
        assert ordinary.device_id == panel_device.id
        assert ordinary.entity_category is None
        assert hass.states.get(ordinary.entity_id).attributes["drives_electric_fence"] is False

        # The output was identified without anyone being asked to identify it. ADR-0017.
        assert issues.async_get_issue(DOMAIN, f"fence_pgm_detected_{panel.serial}") is None
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_stale_fence_pgm_repair_is_deleted(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """An installation upgrading from Sprint 8 has the retired issue sitting in its registry.

    It named a real hazard, but the action it asked for is one the integration now takes itself, so
    leaving it up would be asking the user to fix something already fixed.
    """
    panel = FakePanel(serial="STALEREP01", **FENCE_PGM_PANEL)
    entry = await _entry_for(hass, port, panel)
    issues = ir.async_get(hass)
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"fence_pgm_detected_{panel.serial}",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="fence_pgm_detected",
    )
    assert issues.async_get_issue(DOMAIN, f"fence_pgm_detected_{panel.serial}") is not None
    try:
        _, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        await coordinator.async_read_programming()
        await hass.async_block_till_done()

        assert issues.async_get_issue(DOMAIN, f"fence_pgm_detected_{panel.serial}") is None
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_configured_fence_pgm_that_agrees_raises_nothing(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """When the setting and the programming say the same output, there is nothing to warn about."""
    panel = FakePanel(serial="AGREEPGM01", **FENCE_PGM_PANEL)
    entry = await _entry_for(hass, port, panel, **{CONF_FENCE_PGM: 2})
    try:
        _, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        await coordinator.async_read_programming()
        await hass.async_block_till_done()

        issues = ir.async_get(hass)
        assert issues.async_get_issue(DOMAIN, f"fence_pgm_detected_{panel.serial}") is None
        assert issues.async_get_issue(DOMAIN, f"fence_pgm_conflict_{panel.serial}") is None
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_disagreement_honours_the_setting_and_raises_a_conflict(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """The user set PGM 4; the programming says PGM 2. The setting wins; the clash is surfaced."""
    panel = FakePanel(serial="CONFLICT01", **FENCE_PGM_PANEL)
    entry = await _entry_for(hass, port, panel, **{CONF_FENCE_PGM: 4})
    try:
        _, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        await coordinator.async_read_programming()
        await hass.async_block_till_done()

        # The setting is honoured: PGM 4 drives the fence, the detected PGM 2 does not.
        assert coordinator.capabilities.effective_fence_pgm(4) == 4
        assert coordinator.capabilities.drives_fence(2, configured=4) is False

        issues = ir.async_get(hass)
        assert issues.async_get_issue(DOMAIN, f"fence_pgm_detected_{panel.serial}") is None
        conflict = issues.async_get_issue(DOMAIN, f"fence_pgm_conflict_{panel.serial}")
        assert conflict is not None
        assert conflict.translation_placeholders == {
            "serial": panel.serial,
            "configured": "4",
            "detected": "2",
        }
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_panel_without_a_fence_pgm_raises_nothing(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """A panel whose PGMs are gate, light and siren detects no energiser, and warns of none."""
    panel = FakePanel(serial="NOFENCEPG1", pgm_functions={1: 12, 2: 1, 3: 11})
    entry = await _entry_for(hass, port, panel)
    try:
        _, coordinator = await _bring_up(hass, entry, connect_panel, panel)
        await coordinator.async_read_programming()
        await hass.async_block_till_done()

        assert coordinator.capabilities.detected_fence_pgm is None
        issues = ir.async_get(hass)
        assert issues.async_get_issue(DOMAIN, f"fence_pgm_detected_{panel.serial}") is None
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


# --- 8.1: a panel produces exactly the entities for what it has ----------------------------------


async def test_a_panel_with_no_fence_and_no_pgms_grows_neither(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """An Active 8 Ultra (`0xA2`): two partitions, no PGM outputs, no energiser."""
    panel = FakePanel(serial="ACTIVE8U01", model_byte=0xA2, fence=0x00, zones={1: 0x8, 2: 0x8})
    entry = await _entry_for(hass, port, panel)
    try:
        await _bring_up(hass, entry, connect_panel, panel)
        entities = er.async_get(hass)
        unique_ids = {
            e.unique_id for e in er.async_entries_for_config_entry(entities, entry.entry_id)
        }

        assert not any("-pgm" in uid for uid in unique_ids), "no PGM switches on a panel with none"
        assert f"{panel.serial}-fence-switch" not in unique_ids, "and no fence entity"
        # It does have partitions, so it is not simply an empty integration.
        assert any("-partition" in uid for uid in unique_ids)
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_a_module_grows_no_partition(hass: HomeAssistant, port: int, connect_panel) -> None:
    """An M-300+ (`0x4B`) reports events and drives PGMs, but has nothing to arm."""
    panel = FakePanel(
        serial="MODULE0001",
        model_byte=0x4B,
        partitions=[0x00, 0x00, 0x00, 0x00],
        fence=0x00,
        zones={},
    )
    entry = await _entry_for(hass, port, panel)
    try:
        await _bring_up(hass, entry, connect_panel, panel)
        entities = er.async_get(hass)
        unique_ids = {
            e.unique_id for e in er.async_entries_for_config_entry(entities, entry.entry_id)
        }

        assert not any("-partition" in uid for uid in unique_ids), "a module has no partitions"
        assert f"{panel.serial}-fence-switch" not in unique_ids
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

"""Partitions, as alarm control panels.

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

**The partition offers the two arm modes a user actually arms with**, and the mapping is not the
obvious one — it comes from the panel manual §3.2-3.4 rather than from the names:

| Keypad | Command | Home Assistant | Why |
|---|---|---|---|
| Armar | `0x4E` | `ARM_AWAY` | The ordinary full arm. Refused while a zone is open |
| Armar STAY | `0x53` | `ARM_HOME` | Perimeter only, so somebody can stay inside |
| Armar AWAY | `0x54` | *not exposed* | A **forced** arm — see below |

JFL's "AWAY" is a *forced* arm, not Home Assistant's "armed away": it inhibits whatever is open and
restores each zone as it closes. It was exposed as `ARM_CUSTOM_BYPASS` until 2026-08-09, when the
author tested all three against the panel and **decided to remove it** — three buttons where a user
needs two, and the panel cannot tell the two "away" arms apart in the state it reports back, so the
third button was indistinguishable from the first once pressed. `ArmMode.AWAY` remains a valid
command in the protocol layer; it simply is not a Home Assistant arm button.
ADR-0016 supersedes ADR-0003.

**The panel reports only two states back.** `PART[i]` reads `0x02` for both the ordinary arm and the
forced one, and both emit event `3407`; only STAY is distinguishable, as `0x03`.

`supported_features` comes from the **model**, never from `P-PART`: those permission bits are
state-dependent — the 2026-08-08 capture read `0x0B` while disarmed and `0x1F` while armed — so
deriving features from them makes buttons appear and disappear on their own. The bits are checked
instead at the moment a command is sent, in the coordinator, which can then name the address to fix.

**The electric fence is deliberately not here.** It has no stay, no away and no entry delay: it is
armed or it is not. Home Assistant has no plain "armed" state, so an alarm panel would have to
report it as "armed away", which is a claim the fence cannot support. It is a `switch` with a state
`sensor` beside it — see `switch.py` and `docs/development/entity-map.md`.

**These entities deliberately do not restore their state across a restart.** A restored state is a
*claim about the present made from the past*, and the claim this one would make is "the house is
disarmed" — for a house that may have been armed while Home Assistant was down. Availability is
driven by the panel's connection, so until the panel reports, these entities read `unavailable`,
which is true.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import (
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from pyjfl import ArmMode

from .const import (
    CONF_CODE,
    CONF_CODE_ARM_REQUIRED,
    CONF_SERIAL,
    DEFAULT_CODE,
    DEFAULT_CODE_ARM_REQUIRED,
    DOMAIN,
    SUBENTRY_TYPE_PANEL,
)
from .entity import JflPartitionEntity, async_add_discovered

if TYPE_CHECKING:
    from homeassistant.helpers.entity import Entity
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import JflConfigEntry
    from .coordinator import JflPanelCoordinator, JflPanelState

PARALLEL_UPDATES = 1
"""This platform sends commands. One at a time — AGENTS.md §5."""

PARTITION_FEATURES = (
    AlarmControlPanelEntityFeature.ARM_AWAY | AlarmControlPanelEntityFeature.ARM_HOME
)
"""What every JFL partition offers. Two entries, not three.

`ARM_CUSTOM_BYPASS` was removed on the author's decision after testing all three against the real
panel (ADR-0016): the forced arm is redundant with the plain arm from a user's point of view, and
the panel reports both identically afterwards.

`TRIGGER` is absent for a different reason: nothing in the command set fires an alarm on demand, and
offering a button that silently does nothing is worse than not offering it."""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JflConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create an alarm panel per programmed partition."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_PANEL:
            continue
        coordinator = entry.runtime_data.coordinators[str(subentry.data[CONF_SERIAL])]
        async_add_discovered(coordinator, async_add_entities, partial(_discover, coordinator))


@callback
def _discover(coordinator: JflPanelCoordinator, state: JflPanelState) -> list[Entity]:
    """Return the partitions that exist on this panel and have not been created yet."""
    found: list[Entity] = []
    for index, partition in enumerate(state.partitions, start=1):
        # `programmed` is the panel's own answer to "does this partition exist here?". A
        # four-partition model with one partition in use must produce one entity, not four.
        if not partition.programmed or index in coordinator.discovered.partitions:
            continue
        coordinator.discovered.partitions.add(index)
        found.append(JflPartitionAlarm(coordinator, index))
    return found


class JflPartitionAlarm(JflPartitionEntity, AlarmControlPanelEntity):
    """One programmed partition, with the two arm modes a user actually arms with."""

    _attr_name = None
    """The partition sub-device carries the name, so the entity inherits the device's."""

    _attr_supported_features = PARTITION_FEATURES

    def __init__(self, coordinator: JflPanelCoordinator, partition: int) -> None:
        """Create the entity for *partition*, 1-based."""
        super().__init__(coordinator, partition, "alarm")
        code = str(coordinator.subentry.data.get(CONF_CODE, DEFAULT_CODE) or "")
        self._code = code
        # An all-digit code gets the numeric keypad; anything else gets a text field. Setting a
        # format with no code configured would make Home Assistant demand one that can never match.
        self._attr_code_format = None if not code else CodeFormat.NUMBER
        if code and not code.isdigit():
            self._attr_code_format = CodeFormat.TEXT
        self._attr_code_arm_required = bool(code) and bool(
            coordinator.subentry.data.get(CONF_CODE_ARM_REQUIRED, DEFAULT_CODE_ARM_REQUIRED)
        )

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Map `PART[i]` to a Home Assistant alarm state.

        `TRIGGERED` wins over the arm mode: a partition in alarm is in alarm whether it was armed
        away or at home, and that is the fact a dashboard has to show first.
        """
        state = self.snapshot.partition(self.partition)
        if state is None or not state.programmed:
            return None
        if state.triggered:
            return AlarmControlPanelState.TRIGGERED
        if state.armed_away:
            # `0x02` covers both the ordinary arm and the forced one. The panel does not distinguish
            # them, so neither does this — inferring "custom bypass" from our own memory of which
            # button was pressed would be a claim about the present made from the past.
            return AlarmControlPanelState.ARMED_AWAY
        if state.armed_stay:
            # JFL calls it STAY; Home Assistant's nearest state is ARMED_HOME. There is no
            # ARMED_STAY, and mapping it to ARMED_NIGHT would be an invention.
            return AlarmControlPanelState.ARMED_HOME
        if state.disarmed:
            return AlarmControlPanelState.DISARMED
        return None

    @property
    def extra_state_attributes(self) -> dict[str, bool]:
        """Expose readiness, which the alarm panel domain has no state for.

        `P-PART` bit 4 is the panel's own "this partition can be armed right now": no open zones. It
        is what decides whether the ordinary arm will be accepted or whether the forced one is
        needed, and an automation needs it *before* it tries.
        """
        status = self.snapshot.status
        if status is None or not 1 <= self.partition <= len(status.partition_permissions):
            return {}
        return {"ready": status.partition_permissions[self.partition - 1].ready}

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm this partition. The code, if one is configured, is always required here."""
        self._validate_code(code)
        await self.coordinator.async_disarm(self.partition)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Arm everything — the keypad's plain **Armar**. The panel refuses it if a zone is open."""
        await self._async_arm(ArmMode.TOTAL, code)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Arm the perimeter only — the keypad's **Armar STAY**, so somebody can stay inside."""
        await self._async_arm(ArmMode.STAY, code)

    async def _async_arm(self, mode: ArmMode, code: str | None) -> None:
        if self.code_arm_required:
            self._validate_code(code)
        await self.coordinator.async_arm(self.partition, mode)

    def _validate_code(self, code: str | None) -> None:
        """Check the Home Assistant-side code, if the user configured one.

        Nothing here goes anywhere near the panel: the commands this integration sends carry no
        password at all. This is the lock on the tablet in the hallway, and a wrong code raises
        rather than returning quietly — a disarm that silently does nothing is the worst possible
        outcome for an alarm.
        """
        if not self._code:
            return
        if code != self._code:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_code",
            )

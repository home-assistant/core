"""Partitions, as alarm control panels.

The panel keypad's "Armar" (`0x4E`) maps to `ARM_AWAY` and "Armar STAY" (`0x53`) to `ARM_HOME`. The
panel's third mode, "Armar AWAY" (`0x54`), is a forced arm that inhibits whatever is open; it is not
exposed, because the panel reports it back in the same state as the ordinary arm and the two would
be indistinguishable once pressed.

`supported_features` comes from the model, never from the panel's `P-PART` permission bits: those
are state-dependent, so deriving features from them would make buttons appear and disappear on their
own. They are checked instead at the moment a command is sent.

These entities do not restore their state across a restart. The claim a restored state would make is
"the house is disarmed", for a house that may have been armed while Home Assistant was down.
"""

from functools import partial
from typing import TYPE_CHECKING, override

from pyjfl import ArmMode

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.const import CONF_CODE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError

from .const import (
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
"""This platform sends commands, one at a time."""

PARTITION_FEATURES = (
    AlarmControlPanelEntityFeature.ARM_AWAY | AlarmControlPanelEntityFeature.ARM_HOME
)
"""What every JFL partition offers. Two entries, not three.

`ARM_CUSTOM_BYPASS` is not offered: the panel's forced arm is redundant with the plain arm from a
user's point of view, and the panel reports both identically afterwards.

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
        async_add_discovered(
            coordinator, async_add_entities, partial(_discover, coordinator)
        )


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
            coordinator.subentry.data.get(
                CONF_CODE_ARM_REQUIRED, DEFAULT_CODE_ARM_REQUIRED
            )
        )

    @property
    @override
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

    @override
    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm this partition. The code, if one is configured, is always required here."""
        self._validate_code(code)
        await self.coordinator.async_disarm(self.partition)

    @override
    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Arm everything — the keypad's plain **Armar**. The panel refuses it if a zone is open."""
        await self._async_arm(ArmMode.TOTAL, code)

    @override
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

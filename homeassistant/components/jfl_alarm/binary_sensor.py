"""Zones, zone faults, panel trouble flags, connectivity and the siren.

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

**A zone produces five entities, not one, and it is its own device.** Its nibble encodes six
different things — open, triggered, not communicating, short circuit, tamper, low battery — and
folding them into a single "open" sensor makes that word mean six different things, which is how a
user ends up with an automation that fires because a sensor's battery died. So:

* `opening` — is the sensor physically open? `OPEN` and `TRIGGERED` both count.
* `battery` — low battery. The one wireless-health entity enabled by default, because it is the one
  that predicts a sensor going silent next month.
* `connectivity` — is the panel still hearing from this sensor? **On means connected**, which is the
  device class's own direction, so a supervision failure reads `off`.
* `tamper` — its own device class, because Home Assistant has one and it means something specific.
* `problem` — the aggregate fault, kept for the one thing the others do not cover on their own: a
  short circuit on a hard-wired zone.

**Battery, supervision and tamper are merged from two sources**, and neither alone is enough. The
nibble is present-tense but holds a single value, so a sensor with a dying battery reports `6` while
closed and `7` the moment somebody walks past it — the low battery has not gone away, it has been
overwritten. Contact ID `1384`/`3384`, `1381`/`3381` and `1383`/`3383` bracket the condition
independently, and the coordinator latches them. Either source saying yes is a yes; see
`JflPanelState.zone_alert` and `docs/adr/0008-zone-alerts-merge-two-sources.md`.

The panel's own trouble flags in `PROB[5]` become one diagnostic `problem` sensor each, plus an
aggregate so a dashboard can show "something is wrong" without listing thirty-two bits.

The electric fence contributes one sensor here: **is it in alarm**, with `device_class: safety`.
That is a separate entity from the fence switch on purpose — a triggered fence is still an armed
fence, and folding "in alarm" into the switch's on/off would make switching it off look like the way
to clear an alarm.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from pyjfl import ZONE_TYPE_NAMES, ProblemFlag, ZoneAlert, ZoneStatus

from .const import (
    CONF_SERIAL,
    CONF_ZONE_POLICY,
    DEFAULT_ZONE_POLICY,
    SUBENTRY_TYPE_PANEL,
    ZONES_ALL,
)
from .entity import JflEntity, JflFenceEntity, JflZoneEntity, async_add_discovered

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.helpers.entity import Entity
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import JflConfigEntry
    from .coordinator import JflPanelCoordinator, JflPanelState

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class JflProblemDescription(BinarySensorEntityDescription):
    """A `PROB` bit, with the flag it reads."""

    flag: ProblemFlag


PROBLEM_FLAGS: tuple[JflProblemDescription, ...] = tuple(
    JflProblemDescription(
        key=f"problem_{flag.name.lower()}",
        translation_key=f"problem_{flag.name.lower()}",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=flag
        in (
            # The four an ordinary user acts on. The rest are installer territory: present, but not
            # switched on by default, so thirty-two diagnostic entities do not arrive uninvited.
            ProblemFlag.AC_MAINS,
            ProblemFlag.BATTERY,
            ProblemFlag.TAMPER,
            ProblemFlag.SIREN,
        ),
        flag=flag,
    )
    for flag in ProblemFlag
)


@dataclass(frozen=True, kw_only=True)
class JflPanelBinaryDescription(BinarySensorEntityDescription):
    """A panel-level binary sensor computed from the snapshot."""

    value_fn: Callable[[JflPanelState], bool | None]


PANEL_SENSORS: tuple[JflPanelBinaryDescription, ...] = (
    JflPanelBinaryDescription(
        key="connectivity",
        translation_key="connectivity",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.available,
    ),
    JflPanelBinaryDescription(
        key="problem",
        translation_key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda state: state.status.problems.any if state.status else None,
    ),
    JflPanelBinaryDescription(
        key="siren",
        translation_key="siren",
        # Read-only, so a `binary_sensor` with device class `sound` and never a `siren` entity:
        # the siren domain models something you can switch, and we cannot. See the entity map.
        device_class=BinarySensorDeviceClass.SOUND,
        value_fn=lambda state: bool(state.status.siren) if state.status else None,
    ),
    JflPanelBinaryDescription(
        key="updating",
        translation_key="updating",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.status.updating if state.status else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JflConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the panel-level binary sensors now and the zone sensors as zones appear."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_PANEL:
            continue
        coordinator = entry.runtime_data.coordinators[str(subentry.data[CONF_SERIAL])]
        all_zones = subentry.data.get(CONF_ZONE_POLICY, DEFAULT_ZONE_POLICY) == ZONES_ALL

        # The panel-level sensors need nothing from the panel to exist, so they are added at once —
        # the connectivity sensor in particular has to be there to say "not connected".
        async_add_entities(
            [JflPanelBinarySensor(coordinator, description) for description in PANEL_SENSORS]
            + [JflProblemSensor(coordinator, description) for description in PROBLEM_FLAGS],
            config_subentry_id=subentry.subentry_id,
        )
        async_add_discovered(
            coordinator,
            async_add_entities,
            partial(_discover_zones, coordinator, all_zones=all_zones),
        )
        async_add_discovered(coordinator, async_add_entities, partial(_discover_fence, coordinator))


@callback
def _discover_fence(coordinator: JflPanelCoordinator, state: JflPanelState) -> list[Entity]:
    """Return the fence's alarm sensor, once the panel has said it has a fence."""
    if not state.fence.present or coordinator.discovered.fence_alarm:
        return []
    coordinator.discovered.fence_alarm = True
    return [JflFenceAlarmSensor(coordinator)]


@callback
def _discover_zones(
    coordinator: JflPanelCoordinator, state: JflPanelState, *, all_zones: bool
) -> list[Entity]:
    """Return the zone entities that exist and have not been created yet.

    The protocol layer drops zones whose nibble reads `DISABLED` — they are not in use on this
    installation, and by default they get no entity. The `all` policy cannot simply look at what
    the decoder returned, then: it has to walk the model's own zone range and fill in the gaps, and
    the zones it adds report `unknown` until the installer programs them.
    """
    if state.status is None:
        # Nothing has been read yet. Zone 1 not existing and zone 1 not having been reported are
        # different things, and creating entities for the second would create all of them.
        return []

    numbers = [zone.number for zone in state.zones]
    if all_zones:
        numbers = list(range(1, state.spec.zones + 1))

    found: list[Entity] = []
    for number in numbers:
        if number in coordinator.discovered.zones:
            continue
        coordinator.discovered.zones.add(number)
        found.extend(
            (
                JflZoneSensor(coordinator, number),
                JflZoneProblemSensor(coordinator, number),
                JflZoneTamperSensor(coordinator, number),
                JflZoneBatterySensor(coordinator, number),
                JflZoneConnectivitySensor(coordinator, number),
            )
        )
    return found


class JflPanelBinarySensor(JflEntity, BinarySensorEntity):
    """A binary sensor computed straight from the snapshot."""

    entity_description: JflPanelBinaryDescription

    def __init__(
        self, coordinator: JflPanelCoordinator, description: JflPanelBinaryDescription
    ) -> None:
        """Create the sensor described by *description*."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """The described value, or `None` before the first status frame."""
        return self.entity_description.value_fn(self.snapshot)

    @property
    def available(self) -> bool:
        """The connectivity sensor is the one entity that must work while the panel is away.

        An entity that reports "not connected" is useless if being disconnected makes it
        unavailable, so this one is always available once it exists.
        """
        if self.entity_description.device_class is BinarySensorDeviceClass.CONNECTIVITY:
            return True
        return super().available


class JflProblemSensor(JflEntity, BinarySensorEntity):
    """One bit of `PROB[5]`."""

    entity_description: JflProblemDescription

    def __init__(
        self, coordinator: JflPanelCoordinator, description: JflProblemDescription
    ) -> None:
        """Create the sensor for one trouble flag."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """True while the panel reports this trouble."""
        status = self.snapshot.status
        if status is None:
            return None
        return self.entity_description.flag in status.problems


class JflFenceAlarmSensor(JflFenceEntity, BinarySensorEntity):
    """Whether the electric fence is in alarm."""

    _attr_translation_key = "fence_alarm"
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    """`safety` is Home Assistant's "unsafe / safe", which is precisely what a fence in alarm is.
    Not `problem`: a triggered perimeter is not a malfunction, and not `tamper`, which means someone
    is interfering with a *sensor*."""

    def __init__(self, coordinator: JflPanelCoordinator) -> None:
        """Create the fence alarm sensor for this panel."""
        super().__init__(coordinator, "alarm")

    @property
    def is_on(self) -> bool | None:
        """True while the fence is in alarm, armed or not.

        A cut or broken wire keeps the panel in alarm and **never restores itself** — the manual is
        explicit about it — so this is a state somebody has to go and clear, not a blip.
        """
        fence = self.snapshot.fence
        if not fence.present:
            return None
        return fence.triggered


class _JflZoneEntity(JflZoneEntity, BinarySensorEntity):
    """Shared plumbing for the five sensors a zone produces."""

    def __init__(self, coordinator: JflPanelCoordinator, zone: int, key: str) -> None:
        """Create one of zone *zone*'s sensors."""
        super().__init__(coordinator, zone, key)
        self._attr_translation_placeholders = {"zone": str(zone)}

    @property
    def _status(self) -> ZoneStatus | None:
        zone = self.snapshot.zone(self.zone)
        return zone.status if zone is not None else None


class JflZoneSensor(_JflZoneEntity):
    """Whether the zone is physically open."""

    _attr_name = None
    """The zone's sub-device carries the name, so the opening sensor — the one everybody looks at —
    inherits it and reads simply "Zone 3" rather than "Zone 3 Zone 3"."""

    # `opening` until Sprint 6 can read the zone's programmed type and choose door, window,
    # garage_door or motion. Anything more specific now would be a guess presented as a fact.
    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(self, coordinator: JflPanelCoordinator, zone: int) -> None:
        """Create the opening sensor for zone *zone*."""
        super().__init__(coordinator, zone, "open")

    @property
    def is_on(self) -> bool | None:
        """Return whether the sensor is open, including while it is triggering an alarm."""
        status = self._status
        return status.is_open if status is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """The zone's programmed configuration, once a programming read has fetched it.

        Attributes rather than entities, deliberately. These change only when somebody reprograms
        the panel, so a sensor per flag would be six more rows on a device page that nobody watches
        — AGENTS.md §5 puts installer-facing detail here or on a diagnostic entity, not on the
        dashboard. It is the same shape Sprint 8.2 gave the PGM switches.

        `partitions` is a **list**, because the 2026-08-09 differential proved a zone can belong to
        more than one: zone 9 was assigned to A and B and its record read `0x03`. Anything modelling
        this as a single number would be wrong on the author's own panel.

        The zone **type** reports its raw index always and its *name* only for the values proven
        against real zones. A type shown with a wrong name is worse than one shown as a number —
        ADR-0013.
        """
        record = self.coordinator.programming.zones.get(self.zone)
        if record is None:
            return None
        attributes: dict[str, Any] = {
            "partitions": list(record.partitions),
            "stay": record.stay,
            "smart_zone": record.smart,
            "auto_bypass": record.auto_bypass,
            "silent": record.silent,
            "chime": record.chime,
            "allows_bypass": record.allows_bypass,
            "siren_pulsed": record.siren_pulsed,
            "open_door": record.open_door,
        }
        if record.sensitivity is not None:
            attributes["sensitivity"] = record.sensitivity.name.lower()
        if record.zone_type_index is not None:
            # The raw index always; the label only where it is proven. The list order is known from
            # the programmer app and values 1 and 2 are anchored against real zones, but one
            # observed value falls outside it — so an unproven index reports its number and no name
            # rather than a plausible wrong one. ADR-0013.
            attributes["zone_type_index"] = record.zone_type_index
            label = ZONE_TYPE_NAMES.get(record.zone_type_index)
            if label is not None:
                attributes["zone_type"] = label
        return attributes


class JflZoneProblemSensor(_JflZoneEntity):
    """Whether the zone is in a fault state that is not an opening."""

    _attr_translation_key = "zone_problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: JflPanelCoordinator, zone: int) -> None:
        """Create the fault sensor for zone *zone*."""
        super().__init__(coordinator, zone, "problem")

    @property
    def is_on(self) -> bool | None:
        """True for not communicating, short circuit or low battery — never for tamper.

        Tamper has its own entity: it means someone is interfering with the sensor, which is a
        different thing from the sensor being broken and deserves a different alert. Battery and
        supervision now have their own entities too, and this one deliberately keeps reporting them
        as well — it is the aggregate "this zone is not healthy", and a short circuit has nowhere
        else to appear.
        """
        status = self._status
        if status is None:
            return None
        return status.is_fault and status is not ZoneStatus.TAMPER

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Name the fault, since `problem` on its own does not say which one it is."""
        status = self._status
        return {"zone_status": status.name.lower() if status is not None else "unknown"}


class JflZoneTamperSensor(_JflZoneEntity):
    """Whether someone is interfering with the zone."""

    _attr_translation_key = "zone_tamper"
    _attr_device_class = BinarySensorDeviceClass.TAMPER
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    # **Enabled**, unlike the other two wireless-health sensors, and deliberately against the letter
    # of the sprint plan. Tamper is not diagnostics: it means somebody is opening a detector, which
    # is a break-in signal. It was also enabled in Sprint 2, and disabling it now would silently
    # take an entity away from every installation that already has one.

    def __init__(self, coordinator: JflPanelCoordinator, zone: int) -> None:
        """Create the tamper sensor for zone *zone*."""
        super().__init__(coordinator, zone, "tamper")

    @property
    def is_on(self) -> bool | None:
        """True while the zone reports tamper, from the nibble **or** from events `1383`/`3383`."""
        if self._status is None:
            return None
        return self.snapshot.zone_alert(self.zone, ZoneAlert.TAMPER)


class JflZoneBatterySensor(_JflZoneEntity):
    """Whether a wireless sensor's battery is low.

    **The one wireless-health entity enabled by default.** It is the only one that gives warning
    rather than reporting a fait accompli: a supervision failure means the sensor has already gone
    silent, and this means it is going to.
    """

    _attr_translation_key = "zone_battery"
    _attr_device_class = BinarySensorDeviceClass.BATTERY
    """`on` means **low**, which is the device class's own direction. Not inverted here."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: JflPanelCoordinator, zone: int) -> None:
        """Create the battery sensor for zone *zone*."""
        super().__init__(coordinator, zone, "battery")

    @property
    def is_on(self) -> bool | None:
        """True while the battery is low, from the nibble **or** from events `1384`/`3384`.

        Merged rather than read from the nibble alone, because the nibble holds one value: a sensor
        with a dying battery reports `6` while closed and `7` the moment somebody walks past it.
        The event pair is not overwritten by anything.
        """
        if self._status is None:
            return None
        return self.snapshot.zone_alert(self.zone, ZoneAlert.LOW_BATTERY)


class JflZoneConnectivitySensor(_JflZoneEntity):
    """Whether the panel is still hearing from this zone's sensor."""

    _attr_translation_key = "zone_connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    """`on` means **connected**. So a supervision failure reads `off`, which is the way round every
    other connectivity sensor in Home Assistant works, and the opposite of the underlying flag."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: JflPanelCoordinator, zone: int) -> None:
        """Create the connectivity sensor for zone *zone*."""
        super().__init__(coordinator, zone, "connectivity")

    @property
    def is_on(self) -> bool | None:
        """True while the sensor is being heard from — nibble not `3`, and no live `1381`."""
        if self._status is None:
            return None
        return not self.snapshot.zone_alert(self.zone, ZoneAlert.SUPERVISION)

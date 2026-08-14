"""Diagnostic sensors, and the electric fence's state.

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

Everything here is `EntityCategory.DIAGNOSTIC` bar one: the fence state sensor, which belongs on a
dashboard. The rest belongs in a bug report. What is deliberately **absent** matters as much as what
is present — see `docs/development/entity-map.md`:

* **No firmware, model, serial or MAC sensor.** Those are `DeviceInfo` fields. A firmware version as
  a sensor is never graphed, never automated on, and pushes the things that matter off the screen.
* **The battery percentage is derived, optional and off by default.** The panel reports a voltage,
  `raw / 14`, and that stays the primary sensor. A percentage is genuinely useful — Home Assistant's
  dashboards and voice assistants understand it, and a volt reading means nothing to most people —
  but it is an *interpretation*, so it is opt-in, linear, documented, and never the thing the
  integration shows first. What is rejected is the `Develop-2.0` approach of undocumented buckets
  presented as if the panel had reported them.

**The fence state sensor exists because on/off cannot say everything the panel says.** `ELET` has
five values, and "disarmed and not ready" is not "disarmed". An `ENUM` sensor is the one Home
Assistant primitive whose displayed values an integration may name itself, which is what lets this
one read *Armada* and *Desarmada* rather than borrowing an alarm panel's vocabulary of away and
stay — states an energiser does not have. The switch beside it is how you operate it.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any, Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfElectricPotential, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from pyjfl import SignalQuality

from .const import CONF_SERIAL, SUBENTRY_TYPE_PANEL
from .entity import JflEntity, JflFenceEntity, JflZoneEntity, async_add_discovered

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from homeassistant.helpers.entity import Entity
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
    from pyjfl import WirelessDevice

    from . import JflConfigEntry
    from .coordinator import JflPanelCoordinator, JflPanelState

PARALLEL_UPDATES = 0

BATTERY_EMPTY_VOLTS: Final = 10.5
BATTERY_FULL_VOLTS: Final = 12.5
"""The two ends of the derived battery percentage, and the whole of its definition.

A sealed 12 V lead-acid battery sits near 13 V on float charge and is considered flat at about
10.5 V; the panel's own display calls anything above 12.5 V "100%". So the mapping is linear
between those two, clamped at both ends. It is **an interpretation of a voltage, not a reading** —
which is why the voltage sensor stays primary and this one is disabled by default.
"""


def _battery_percentage(volts: float) -> float:
    """Map *volts* onto 0-100, clamped. See `BATTERY_EMPTY_VOLTS`."""
    span = BATTERY_FULL_VOLTS - BATTERY_EMPTY_VOLTS
    return round(max(0.0, min(100.0, (volts - BATTERY_EMPTY_VOLTS) / span * 100)))


FENCE_STATES: tuple[str, ...] = ("disarmed", "armed", "triggered", "not_ready")
"""The states of `ELET` worth telling a user apart, and the `options` this sensor declares.

`ELET` carries five values, but two of them are another value with the alarm bit set, and the alarm
has its own `safety` sensor. What is left is: off, on, in alarm, and off-but-cannot-be-armed.
"""

FENCE_STATE_OPTIONS: Final = list(FENCE_STATES)
SIGNAL_OPTIONS: Final = [quality.name.lower() for quality in SignalQuality]
"""Both are module constants rather than class-body expressions on purpose. `_attr_options` is an
*instance* attribute on `SensorEntity`, so annotating a subclass copy `ClassVar` is an override
`mypy --strict` rejects — and a bare list comprehension in a class body is what `RUF012` rejects.
Naming the value here satisfies both without either rule having to be switched off."""


@dataclass(frozen=True, kw_only=True)
class JflSensorDescription(SensorEntityDescription):
    """A sensor and the snapshot field it reads."""

    value_fn: Callable[[JflPanelState], float | str | datetime | None]

    survives_disconnect: bool = False
    """Whether this sensor stays available while the panel is silent.

    False for almost everything: a battery voltage from an hour ago is not the battery voltage.
    True for the two that answer "when did it last work?", which are worth reading precisely
    *because* the panel has gone away — blanking them destroys the only clue on offer."""


SENSORS: tuple[JflSensorDescription, ...] = (
    JflSensorDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.status.battery_volts if state.status else None,
    ),
    JflSensorDescription(
        key="battery_level",
        translation_key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        # **Enabled by default at the author's request (2026-08-09).** Sprint 5 shipped it off, on
        # the grounds that it is this project's interpretation of a voltage rather than something
        # the panel said. That is still true and still documented — but a percentage is what Home
        # Assistant's battery cards, voice assistants and low-battery blueprints actually consume,
        # and a diagnostic entity nobody turns on helps nobody. The voltage remains the primary
        # sensor, and this one reports `unknown` rather than 0% when no battery is fitted.
        value_fn=lambda state: (
            _battery_percentage(state.status.battery_volts)
            # `0` is the panel saying **no battery is fitted**, not a flat one, and mapping that to
            # 0% would put a false alarm on the dashboard of every panel running without a battery.
            if state.status and state.status.battery_volts > 0
            else None
        ),
    ),
    JflSensorDescription(
        key="last_connected",
        translation_key="last_connected",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        # Kept after the panel goes away, deliberately: at three in the afternoon, "it last
        # connected at 14:02" is the useful fact, and blanking it would destroy it.
        survives_disconnect=True,
        value_fn=lambda state: state.connected_since,
    ),
    JflSensorDescription(
        key="last_seen",
        translation_key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        # The liveness signal that can be trusted. A TCP socket stays open long after the box at
        # the far end has lost power, so "connected" is a weaker claim than "spoke to us recently".
        # Every frame stamps this, including keep-alives that carry nothing else.
        survives_disconnect=True,
        value_fn=lambda state: state.last_seen_at,
    ),
    JflSensorDescription(
        key="last_event",
        translation_key="last_event",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.last_event_at,
    ),
    JflSensorDescription(
        key="signal",
        translation_key="signal",
        # No `SIGNAL_STRENGTH` device class: that one means dBm, and the panel reports a bare level
        # with no documented unit. Claiming dBm would put a wrong unit on a right number.
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        # Only a panel with a cellular module reports anything here; an Ethernet-only panel sends
        # 0x00 for ever. Disabled by default rather than absent, because whether a given
        # installation has a SIM in it is not something the connection frame states outright.
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.connection.signal if state.connection else None,
    ),
    JflSensorDescription(
        key="panel_clock",
        translation_key="panel_clock",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        # Text, not a timestamp: the panel sends local time with no timezone, so turning it into an
        # aware datetime would mean asserting a timezone the frame does not carry. Its value is that
        # you can see the panel's clock has drifted, which reading it as text does perfectly well.
        value_fn=lambda state: state.status.clock if state.status else None,
    ),
    JflSensorDescription(
        key="programming_checksum",
        translation_key="programming_checksum",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        # KP changes when, and only when, the panel's programming changes — so it tells an installer
        # that somebody reprogrammed the panel behind their back.
        value_fn=lambda state: (
            state.status.programming_checksum.hex().upper() if state.status else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JflConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the diagnostic sensors. None of them needs the panel to have connected yet."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_PANEL:
            continue
        coordinator = entry.runtime_data.coordinators[str(subentry.data[CONF_SERIAL])]
        async_add_entities(
            [JflSensor(coordinator, description) for description in SENSORS],
            config_subentry_id=subentry.subentry_id,
        )
        async_add_discovered(coordinator, async_add_entities, partial(_discover_fence, coordinator))
        async_add_discovered(
            coordinator, async_add_entities, partial(_discover_wireless, coordinator)
        )
        async_add_discovered(
            coordinator, async_add_entities, partial(_discover_timers, coordinator)
        )


TIMERS: Final[tuple[tuple[str, str, str], ...]] = (
    # key, attribute on `TimerSettings`, unit
    ("entry_1", "entry_1_seconds", UnitOfTime.SECONDS),
    ("entry_2", "entry_2_seconds", UnitOfTime.SECONDS),
    ("exit_1", "exit_1_seconds", UnitOfTime.SECONDS),
    ("exit_2", "exit_2_seconds", UnitOfTime.SECONDS),
    ("open_door", "open_door_minutes", UnitOfTime.MINUTES),
    ("smart_zone", "smart_zone_seconds", UnitOfTime.SECONDS),
    ("ac_loss", "ac_loss_minutes", UnitOfTime.MINUTES),
    ("line_loss", "line_loss_minutes", UnitOfTime.MINUTES),
)
"""The panel's programmed timers, as diagnostic sensors.

**The units are per timer and that is the point of this table.** Entry, exit and the smart-zone
window are seconds; open-door, mains-loss and line-loss are minutes. Publishing them all in one unit
would give plausible numbers that are wrong by a factor of sixty, which is exactly the mistake
`TimerSettings` exists to prevent — so the unit travels with the field.

The autotest interval is absent: it carries its own unit in a bit, so it cannot share this shape and
is exposed as an attribute of the panel's programming instead."""


@callback
def _discover_timers(coordinator: JflPanelCoordinator, state: JflPanelState) -> list[Entity]:
    """Return the timer sensors, once a programming read has produced them."""
    if coordinator.programming.timers is None or coordinator.discovered.timers:
        return []
    coordinator.discovered.timers = True
    return [JflTimerSensor(coordinator, key, field, unit) for key, field, unit in TIMERS]


class JflTimerSensor(JflEntity, SensorEntity):
    """One of the panel's programmed timers.

    `None` rather than `0` for a disabled timer: the panel writes `0xFF` to mean *off*, and a
    zero-second entry delay is a different and much more alarming claim.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.DURATION

    def __init__(self, coordinator: JflPanelCoordinator, key: str, field: str, unit: str) -> None:
        """Create the sensor for the timer named *key*."""
        super().__init__(coordinator, f"timer-{key}")
        self._field = field
        self._attr_translation_key = f"timer_{key}"
        self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self) -> int | None:
        """The timer's value in its own unit, or `None` when it is disabled or unread."""
        timers = self.coordinator.programming.timers
        if timers is None:
            return None
        value = getattr(timers, self._field)
        return int(value) if value is not None else None


@callback
def _discover_wireless(coordinator: JflPanelCoordinator, state: JflPanelState) -> list[Entity]:
    """Return signal and last-transmission sensors for each radio detector the panel knows about.

    Discovered from the `0x59` inventory rather than from the enrolment table, because the inventory
    is what carries a *condition* — a zone can be enrolled and never heard from. Entities appear
    after the first programming read, which is also when the inventory is fetched.
    """
    entities: list[Entity] = []
    for zone in sorted(coordinator.programming.inventory):
        if zone in coordinator.discovered.wireless_zones or zone < 1:
            continue
        coordinator.discovered.wireless_zones.add(zone)
        entities += [
            JflZoneSignalSensor(coordinator, zone),
            JflZoneLastSeenSensor(coordinator, zone),
        ]
    return entities


class _JflWirelessSensor(JflZoneEntity, SensorEntity):
    """Base for a sensor reading one radio detector's live condition.

    Availability follows the *inventory*, not the panel: a detector that has dropped out of the
    inventory has genuinely stopped being described, and an entity that kept showing its last known
    signal would be claiming knowledge the panel no longer has.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def device(self) -> WirelessDevice | None:
        """The inventory record for this zone, or `None` if it is not in the current inventory."""
        return self.coordinator.programming.inventory.get(self.zone)

    @property
    def available(self) -> bool:
        """Available only while the panel is connected *and* still reports this detector."""
        return super().available and self.device is not None


class JflZoneSignalSensor(_JflWirelessSensor):
    """How well the panel hears this radio detector.

    An **enum**, not a percentage or a dBm figure, because that is what the panel reports: four
    named steps confirmed against the manufacturer's own UI. Inventing a percentage from a
    four-value scale would dress a guess as a measurement.
    """

    _attr_translation_key = "zone_signal"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = SIGNAL_OPTIONS

    def __init__(self, coordinator: JflPanelCoordinator, zone: int) -> None:
        """Create the signal sensor for wireless zone *zone*."""
        super().__init__(coordinator, zone, "signal")

    @property
    def native_value(self) -> str | None:
        """The link quality as a lower-case `SignalQuality` name."""
        device = self.device
        return device.signal.name.lower() if device is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """The repeater the detector arrives through, its firmware, and its model.

        `repeater` is `0` for a direct link. All three are attributes rather than their own
        entities because they change only when somebody moves or swaps a detector, and none of
        them means anything without the signal reading they qualify. `model` is repeated here
        even on a Home Assistant version whose zone device page also carries it (`device.py`'s
        `build_zone_device`, pre-2026.9): on 2026.9+ the device page cannot show it at all, since
        the child-device mechanism has no `model` field, so this is the one place guaranteed to
        have it either way.
        """
        device = self.device
        if device is None:
            return None
        radio = self.coordinator.programming.wireless_for_zone(self.zone)
        return {
            "repeater": device.repeater,
            "firmware": device.firmware,
            "serial": device.serial,
            "model": (radio.model or "") if radio is not None else "",
        }


class JflZoneLastSeenSensor(_JflWirelessSensor):
    """When this radio detector last transmitted, as the panel recorded it.

    A plain timestamp string rather than a `timestamp` device class: the panel reports local wall
    time with no timezone, and presenting it as an absolute instant would be a claim the data does
    not support. `sensor.<panel>_last_seen` is the entity to trust for "is the panel alive"; this
    one answers "is this *detector* alive".
    """

    _attr_translation_key = "zone_last_transmission"

    def __init__(self, coordinator: JflPanelCoordinator, zone: int) -> None:
        """Create the last-transmission sensor for wireless zone *zone*."""
        super().__init__(coordinator, zone, "last_transmission")

    @property
    def native_value(self) -> str | None:
        """`DD/MM/YY HH:MM:SS` as the panel keeps it, or `None` if the field was malformed."""
        device = self.device
        return (device.last_seen or None) if device is not None else None


@callback
def _discover_fence(coordinator: JflPanelCoordinator, state: JflPanelState) -> list[Entity]:
    """Return the fence state sensor, once the panel has said it has a fence."""
    if not state.fence.present or coordinator.discovered.fence_state:
        return []
    coordinator.discovered.fence_state = True
    return [JflFenceStateSensor(coordinator)]


class JflFenceStateSensor(JflFenceEntity, SensorEntity):
    """The electric fence's state, in the panel's own vocabulary."""

    _attr_translation_key = "fence_state"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = FENCE_STATE_OPTIONS

    def __init__(self, coordinator: JflPanelCoordinator) -> None:
        """Create the fence state sensor for this panel."""
        super().__init__(coordinator, "state")

    @property
    def native_value(self) -> str | None:
        """Return one of `FENCE_STATES`, or `None` before the panel has reported.

        The alarm flag is checked first and wins: a fence in alarm is in alarm whether it was armed
        or not, and that is the fact worth showing. `0x04`, "disarmed and not ready", is kept
        distinct from an ordinary disarm — it is the difference between a fence you can switch on
        and one that will refuse.
        """
        fence = self.snapshot.fence
        if not fence.present:
            return None
        if fence.triggered:
            return "triggered"
        if fence.armed:
            return "armed"
        if not fence.ready:
            return "not_ready"
        if fence.disarmed:
            return "disarmed"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, int | bool]:
        """The raw byte and the two permission bits, for an installer chasing a refused command."""
        fence = self.snapshot.fence
        status = self.snapshot.status
        permissions = status.fence_permissions if status is not None else None
        return {
            "raw": fence.raw,
            "can_arm": permissions.may_arm if permissions is not None else False,
            "can_disarm": permissions.may_disarm if permissions is not None else False,
        }


class JflSensor(JflEntity, SensorEntity):
    """A diagnostic value read straight out of the snapshot."""

    entity_description: JflSensorDescription

    def __init__(self, coordinator: JflPanelCoordinator, description: JflSensorDescription) -> None:
        """Create the sensor described by *description*."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | str | datetime | None:
        """The described value, or `None` before the panel has reported."""
        return self.entity_description.value_fn(self.snapshot)

    @property
    def available(self) -> bool:
        """Follow the panel, except for the sensors that exist to describe its absence."""
        if self.entity_description.survives_disconnect:
            return True
        return super().available

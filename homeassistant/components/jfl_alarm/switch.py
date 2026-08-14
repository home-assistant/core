"""The electric fence, and the master switch that gates every outbound command.

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

**The fence is a switch, not an alarm panel, and that was decided against the alternative.** It
arms, disarms and triggers, which makes an `alarm_control_panel` tempting — but that domain has no
plain "armed" state. Its armed states are `ARMED_AWAY`, `ARMED_HOME`, `ARMED_NIGHT`,
`ARMED_VACATION` and `ARMED_CUSTOM_BYPASS`, all of which mean something the fence cannot mean, and
none of which Home Assistant lets an integration rename. A fence reported as "armed away" is simply
wrong: an energiser has no away, no stay and no entry delay. It is on or it is off.

So the fence is three entities, each of which says one true thing:

* this `switch` — on means armed, and switching it sends `0x4E`/`0x4F` with partition `0x63`;
* a `binary_sensor` with `device_class: safety` — the fence is in alarm (`binary_sensor.py`);
* an enumerated `sensor` — the full state in the panel's own vocabulary (`sensor.py`).

The master command switch is the second of the two gates every command has to pass. `read_only`, in
the panel's settings, is the deliberate opt-in; this one is on the dashboard, so an automation or a
guest-mode script can take control away without anyone opening the configuration. It restores its
position across a restart because it is a *setting*, not a claim about the state of the house.

**A PGM's function decides whether its switch exists at all, and what kind of entity it is.** Home
Assistant fixes an entity's device, its entity category and whether it is created enabled at the
moment it *registers*, and never revisits them — so `_discover_pgms` waits for
`pgm_functions_known` rather than creating the switches on the first status frame, as Sprint 4 did.
The status frame carries PGM *states* but never PGM *functions*; deciding from it meant deciding
before the only source that can answer had spoken, and then living with the answer. ADR-0017.

| Function | What is created |
|---|---|
| 18, or 25 on an Active 20 — it triggers the energiser | **nothing**, on a panel that has a fence |
| 0, *desabilitada* — the panel does not use the output | a switch, config category, **disabled** |
| anything else | a switch, a control on the panel's device |

**Why the energiser's output gets no entity, and why that reverses this module's first answer.**
Function 18 is not the fence's mains supply, which is what ADR-0007 assumed and what an earlier
label in this file said: it is a **momentary trigger**, wired to the energiser's *LIGA* terminal and
pulsed for the record's `duration_seconds` (two seconds on the author's panel) to toggle the fence.
So the switch could never be operated anyway — `P-PGM` grants only functions 12 and 13 — its state
reads `off` for ever between pulses, and the one thing it could conceivably do is flip the energiser
behind the fence entity's back. An entity that cannot act, cannot be read and can only mislead is
not made safer by being visible. **The output is still visible where an installer actually looks for
it:** the diagnostics download carries every PGM record with its function and duration.

A panel with **no fence at all** whose programming or `fence_pgm` setting still names an energiser
output keeps ADR-0007's original treatment — a switch on the panel, configuration, disabled —
because there the entity is the only trace of a contradiction worth seeing.

The user's `fence_pgm` setting is an **override** rather than the only source: detection finds
function 18 on its own (`pyjfl.JflCapabilities`, ADR-0011), and a setting that disagrees still wins
and raises `fence_pgm_conflict`.

Zone bypass is a `switch` per zone the panel says may be inhibited. It is `EntityCategory.CONFIG`
because inhibiting a zone is not something to leave a button for on a wall dashboard.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.restore_state import RestoreEntity
from pyjfl import PGM_FUNCTION_LABELS, PgmFunction, ZoneStatus

from .const import (
    CONF_SERIAL,
    CONF_ZONE_POLICY,
    DEFAULT_ZONE_POLICY,
    DOMAIN,
    LOGGER,
    PGM_PLACEMENT_OPTION,
    PGM_PLACEMENT_VERSION,
    SUBENTRY_TYPE_PANEL,
    ZONES_ALL,
)
from .entity import JflEntity, JflFenceEntity, JflZoneEntity, async_add_discovered

if TYPE_CHECKING:
    from homeassistant.helpers.entity import Entity
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import JflConfigEntry
    from .coordinator import JflPanelCoordinator, JflPanelState

PARALLEL_UPDATES = 1
"""This platform sends commands. One at a time — AGENTS.md §5."""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JflConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the master command switch now, and the fence switch once the panel reports one."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_PANEL:
            continue
        coordinator = entry.runtime_data.coordinators[str(subentry.data[CONF_SERIAL])]
        # The master switch is not discovered: it gates commands, so it has to exist before the
        # panel has said anything, and it stays useful while the panel is away.
        async_add_entities(
            [JflCommandsSwitch(coordinator)], config_subentry_id=subentry.subentry_id
        )
        async_add_discovered(coordinator, async_add_entities, partial(_discover, coordinator))


@callback
def _discover(coordinator: JflPanelCoordinator, state: JflPanelState) -> list[Entity]:
    """Return the fence, PGM and bypass switches that exist and have not been created yet."""
    found: list[Entity] = []

    # `ELET == 0x00` means no fence is configured, which is not the same as a disarmed fence.
    # Creating no entity at all is the correct answer — see `docs/protocol/fence.md`.
    if state.fence.present and not coordinator.discovered.fence:
        coordinator.discovered.fence = True
        found.append(JflFenceSwitch(coordinator))

    found.extend(_discover_pgms(coordinator, state))
    found.extend(_discover_bypass(coordinator, state))
    return found


@callback
def _discover_pgms(coordinator: JflPanelCoordinator, state: JflPanelState) -> list[Entity]:
    """Return one switch per PGM the panel can have, once its functions are known.

    The count comes from `JflCapabilities`, not from the model table directly — the one place the
    model, the status frame and the programming are merged.

    **Two things have to have happened**, and the second is what Sprint 4 got wrong. The panel must
    have sent a status frame, so there is something to show; and its *functions* must be settled —
    `pgm_functions_known`, which is a completed programming read or the proof that this panel will
    never answer one. The module docstring has the table those functions decide. Waiting costs the
    switches the first half-minute of a panel's session; deciding early cost them a device, a
    category and an enabled flag that Home Assistant would never revisit.

    `P-PGM` looks like it could answer the same question sooner, and it cannot: it is a
    *permission*, clear both for an output that is not programmed and for one whose function is
    simply not user-operable, so an installer would lose the switch for an output that exists.
    """
    if state.status is None or not coordinator.pgm_functions_known:
        return []
    configured = coordinator.configured_fence_pgm
    capabilities = coordinator.capabilities
    found: list[Entity] = []
    for number in range(1, capabilities.pgms + 1):
        if number in coordinator.discovered.pgms:
            continue
        coordinator.discovered.pgms.add(number)
        record = coordinator.programming.pgms.get(number)
        drives_fence = capabilities.drives_fence(number, configured)
        if drives_fence and capabilities.has_fence:
            _async_drop_row(coordinator, number)
            continue
        switch = JflPgmSwitch(
            coordinator,
            number,
            drives_fence=drives_fence,
            function=record.function if record is not None else None,
        )
        _async_settle_existing_row(coordinator, switch)
        found.append(switch)
    return found


@callback
def _async_drop_row(coordinator: JflPanelCoordinator, number: int) -> None:
    """Delete the registry row of a PGM switch an earlier version created for the energiser.

    Without this the entity does not disappear — it turns grey and reads *no longer provided*, which
    is worse than what it replaced. An entity that is deliberately never created has to have its row
    removed, once, by whoever stopped creating it.

    Safe to call on every discovery run: after the first, there is no row left to find.
    """
    registry = er.async_get(coordinator.hass)
    entity_id = registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, f"{coordinator.serial}-pgm{number}"
    )
    if entity_id is None:
        return
    LOGGER.debug(
        "%s: removing the switch for PGM %d, which triggers the electric fence and is operated "
        "through the fence's own entity",
        coordinator.serial,
        number,
    )
    registry.async_remove(entity_id)


@callback
def _async_settle_existing_row(coordinator: JflPanelCoordinator, switch: JflPgmSwitch) -> None:
    """Apply this switch's default enabled state to a registry row an older version left behind.

    **Home Assistant honours `entity_registry_enabled_default` when it creates a row and never
    again**, on purpose: an entity the user enabled by hand must stay enabled through every upgrade.
    The device and the category *do* follow re-registration, so those correct themselves the first
    time this platform runs — only the disabled flag needs saying out loud, and only for a row that
    predates the decision to say it.

    So it is said exactly once per entity, ever. The marker lives in the entity's own registry
    options, which survive restarts, which means a user who enables the output afterwards keeps it
    enabled: this never runs on that row a second time.
    """
    if switch.unique_id is None:  # pragma: no cover - every entity here sets one
        return
    registry = er.async_get(coordinator.hass)
    entity_id = registry.async_get_entity_id(Platform.SWITCH, DOMAIN, switch.unique_id)
    if entity_id is None:
        return  # A row that does not exist yet is created with the right flags in the first place.
    entry = registry.async_get(entity_id)
    if entry is None:
        return
    settled = entry.options.get(DOMAIN)
    if settled is not None and settled.get(PGM_PLACEMENT_OPTION):
        return
    registry.async_update_entity_options(
        entity_id, DOMAIN, {PGM_PLACEMENT_OPTION: PGM_PLACEMENT_VERSION}
    )
    if switch.disabled_by_default and entry.disabled_by is None:
        LOGGER.debug(
            "%s: PGM %d is not in use on the panel; disabling the switch an earlier version left",
            coordinator.serial,
            switch.number,
        )
        registry.async_update_entity(entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)


@callback
def _discover_bypass(coordinator: JflPanelCoordinator, state: JflPanelState) -> list[Entity]:
    """Return one bypass switch per zone the panel says may be inhibited.

    `P-INIB` is a *programming* choice — the zone's "permite inibir" attribute — rather than the
    state-dependent kind of permission `P-PART` is, so it can be used to decide whether the entity
    exists at all. A zone that may not be bypassed gets no switch, which is more honest than a
    switch that always fails.

    The `all` zone policy overrides that, for an installation still being wired.
    """
    if state.status is None:
        return []
    every_zone = coordinator.subentry.data.get(CONF_ZONE_POLICY, DEFAULT_ZONE_POLICY) == ZONES_ALL
    found: list[Entity] = []
    for zone in state.zones:
        if zone.number in coordinator.discovered.bypass:
            continue
        if not zone.may_bypass and not every_zone:
            continue
        coordinator.discovered.bypass.add(zone.number)
        found.append(JflZoneBypassSwitch(coordinator, zone.number))
    return found


class JflFenceSwitch(JflFenceEntity, SwitchEntity):
    """The electric fence energiser. The project's primary goal."""

    _attr_name = None
    """The fence sub-device carries the name, so the entity inherits the device's."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    """Not `OUTLET`, and deliberately not a `light`-shaped guess: this energises a perimeter."""

    def __init__(self, coordinator: JflPanelCoordinator) -> None:
        """Create the fence switch for this panel."""
        super().__init__(coordinator, "switch")

    @property
    def is_on(self) -> bool | None:
        """True while the energiser is armed.

        A triggered fence is still an *armed* fence — a cut wire does not disarm anything — so the
        alarm flag is masked off here and reported by the safety `binary_sensor` instead.
        """
        fence = self.snapshot.fence
        if not fence.present:
            return None
        return fence.armed

    @property
    def extra_state_attributes(self) -> dict[str, bool]:
        """Expose readiness, which on/off cannot carry.

        `ELET = 0x04` is "disarmed and not ready" — a fence that cannot be armed right now. That is
        what an automation needs to know *before* it tries to switch this on.
        """
        return {"ready": self.snapshot.fence.ready}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Arm the fence. Nobody should be near it."""
        await self.coordinator.async_fence(arm=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disarm the fence."""
        await self.coordinator.async_fence(arm=False)


class JflPgmSwitch(JflEntity, SwitchEntity):
    """One PGM output."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        coordinator: JflPanelCoordinator,
        number: int,
        *,
        drives_fence: bool,
        function: PgmFunction | None,
    ) -> None:
        """Create the switch for PGM *number*, 1-based, and decide where it belongs.

        *drives_fence* is the merged answer — the user's setting if they gave one, otherwise what
        the programming detected (`JflCapabilities.drives_fence`); it is only ever true here on a
        panel that reports **no** fence, since `_discover_pgms` creates nothing for the energiser's
        output on a panel that has one. *function* is what the panel says this output does, or
        `None` for a value no firmware documents.

        Both registry properties are settled **here and only here**, because Home Assistant settles
        them when the entity registers and never revisits them:

        * the **category** — configuration for an output the panel does not use, so it stays out of
          *Controls*. **This mirrors what JFL's own mobile app does** (author's observation,
          2026-08-09): it offers only the outputs that have a purpose;
        * **enabled** — an output the panel has switched off does nothing, so its switch is created
          disabled rather than reporting a permanent `off` nobody can change. It is still *created*:
          an installer can enable it and see that the output is there.
        """
        super().__init__(coordinator, f"pgm{number}")
        self.number = number
        unused = function is PgmFunction.DISABLED
        self._attr_translation_key = "pgm_fence" if drives_fence else "pgm"
        self._attr_translation_placeholders = {"number": str(number)}
        if drives_fence or unused:
            self._attr_entity_category = EntityCategory.CONFIG
        # An output the panel does not use, and — on a panel with no fence at all — one whose
        # function still says energiser. A panel that *has* a fence gets no entity for that output
        # in the first place; `_discover_pgms` returns before reaching this.
        self.disabled_by_default = unused or drives_fence
        """Whether this switch is meant to be created disabled.

        Kept as its own field rather than read back off `_attr_entity_registry_enabled_default`,
        which Home Assistant leaves *unset* unless somebody assigns it — reading it on an ordinary
        switch raises `AttributeError`. `_async_settle_existing_row` uses this to decide whether a
        row an older version created enabled should be told so, once.
        """
        if self.disabled_by_default:
            self._attr_entity_registry_enabled_default = False

    @property
    def drives_fence(self) -> bool:
        """Whether switching this output cuts the electric fence's power.

        Read live rather than remembered from `__init__`, so it stays true if a later read finds a
        reprogrammed panel. The user's setting still wins over detection; the merge is in
        `JflCapabilities.drives_fence`. This is what the toggle warning and the
        `drives_electric_fence` attribute are built on — ADR-0007's residual risk closed at the
        point that matters, the moment somebody flips the switch.
        """
        return self.coordinator.capabilities.drives_fence(
            self.number, self.coordinator.configured_fence_pgm
        )

    @property
    def is_on(self) -> bool | None:
        """True while the output is energised, or `None` before the first status frame."""
        status = self.snapshot.status
        if status is None:
            return None
        return status.pgm_on(self.number)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Whether the panel will accept a command, whether it is the fence's, and its function.

        `can_operate` is `P-PGM`, which is clear both for a PGM that is not programmed and for one
        whose function is not user-operable. It answers "why does this switch do nothing?" without a
        trip to the panel's keypad.

        The function, its activation duration and — for the scheduled function — its on and off
        times come from the programming and only appear once it has been read. They are attributes
        rather than their own entities because they are configuration an installer reads now and
        then, not state a dashboard tracks; a `select` to *change* the function is a write, and
        belongs to Sprint 7.
        """
        status = self.snapshot.status
        attributes: dict[str, Any] = {
            "can_operate": status.pgm_permitted(self.number) if status else False,
            "drives_electric_fence": self.drives_fence,
        }
        record = self.coordinator.programming.pgms.get(self.number)
        if record is not None and record.function is not None:
            attributes["function"] = record.function.name.lower()
            attributes["function_number"] = int(record.function)
            # JFL's own wording for the function, so an installer can match it against the
            # programmer app without translating anything. `PGM_FUNCTION_LABELS`.
            attributes["function_label"] = PGM_FUNCTION_LABELS.get(int(record.function), "")
            attributes["activation_seconds"] = record.duration_seconds
            if record.on_at:
                attributes["on_at"] = record.on_at
            if record.off_at:
                attributes["off_at"] = record.off_at
        return attributes

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Energise the output."""
        await self._async_set(on=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """De-energise the output."""
        await self._async_set(on=False)

    async def _async_set(self, *, on: bool) -> None:
        if self.drives_fence:
            LOGGER.warning(
                "Panel %s: PGM %d drives the electric fence and is being switched %s directly. Use "
                "the fence switch instead — this bypasses the fence's own state",
                self.coordinator.serial,
                self.number,
                "on" if on else "off",
            )
        await self.coordinator.async_pgm(self.number, on=on)


class JflZoneBypassSwitch(JflZoneEntity, SwitchEntity):
    """Whether one zone is inhibited.

    On means bypassed — the zone is excluded from the alarm. That direction is the one the panel
    uses and the one the word means; a switch called "bypass" that is on when the zone is *active*
    would be read wrong by everybody, once.

    **It lives on the zone's own device** (author's request, 2026-08-09). Every zone has been a
    device since Sprint 5, and "inhibit the kitchen sensor" belongs next to that sensor's opening,
    battery and tamper entities rather than on a panel page listing every zone at once.

    Moving it is safe because the `unique_id` does not change: `JflZoneEntity` composes exactly the
    `zone{n}-bypass` this switch already used, so Home Assistant sees a device reassignment rather
    than a new entity, and the `entity_id`, history and automations all survive. That is the same
    "adopt, don't recreate" migration ADR-0009 made for the zone entities themselves.
    """

    _attr_translation_key = "zone_bypass"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: JflPanelCoordinator, zone: int) -> None:
        """Create the bypass switch for zone *zone*, 1-based."""
        super().__init__(coordinator, zone, "bypass")

    @property
    def is_on(self) -> bool | None:
        """True while the panel reports this zone as **manually** bypassed.

        An auto-bypassed zone reads `off` here, and that is correct rather than a limitation: the
        panel keeps reporting its physical state, the auto-bypass is not in the manual bitmap, and
        switching this on and off again would not touch it. Events `1570`/`1573` are where an
        auto-bypass shows up.
        """
        zone = self.snapshot.zone(self.zone)
        if zone is None:
            return None
        return zone.status is ZoneStatus.BYPASSED

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Inhibit the zone."""
        await self.coordinator.async_bypass(self.zone, bypassed=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Bring the zone back into the alarm."""
        await self.coordinator.async_bypass(self.zone, bypassed=False)


class JflCommandsSwitch(JflEntity, SwitchEntity, RestoreEntity):
    """The master gate: while this is off, the integration sends the panel no commands at all."""

    _attr_translation_key = "commands_enabled"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, coordinator: JflPanelCoordinator) -> None:
        """Create the master command switch for this panel."""
        super().__init__(coordinator, "commands_enabled")

    @property
    def available(self) -> bool:
        """Always available. It is a setting, and settings do not depend on the panel being awake.

        Turning commands off while a panel is unreachable is a perfectly sensible thing to do, and
        an unavailable switch could not be turned off at all.
        """
        return True

    @property
    def is_on(self) -> bool:
        """Whether outbound commands are currently allowed by this gate."""
        return self.coordinator.commands_enabled

    async def async_added_to_hass(self) -> None:
        """Restore the position this switch was left in.

        Restoring is right here and wrong for the alarm entities, and the difference is what the
        state *is*. An alarm panel's restored state would be a claim about the house — "it is
        disarmed" — made from before the restart. This is a claim about a preference the user
        expressed, which a restart does not change.
        """
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in ("on", "off"):
            self.coordinator.commands_enabled = last.state == "on"
            LOGGER.debug(
                "%s: commands %s, restored",
                self.coordinator.serial,
                "enabled" if self.coordinator.commands_enabled else "disabled",
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Allow commands to be sent, if `read_only` also allows it."""
        self._set(enabled=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop every outbound command at once, without touching the configuration."""
        self._set(enabled=False)

    @callback
    def _set(self, *, enabled: bool) -> None:
        self.coordinator.commands_enabled = enabled
        LOGGER.debug(
            "%s: commands %s", self.coordinator.serial, "enabled" if enabled else "disabled"
        )
        self.async_write_ha_state()

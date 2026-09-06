"""Component providing support for RainMachine programs and zones."""

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Concatenate, override

from regenmaschine.errors import RainMachineError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ID, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import VolDictType

from . import RainMachineConfigEntry, RainMachineData
from .const import DATA_PROGRAMS, DATA_RESTRICTIONS_UNIVERSAL, DATA_ZONES
from .entity import RainMachineEntity, RainMachineEntityDescription
from .services import async_update_programs_and_zones
from .util import RUN_STATE_MAP, key_exists

ATTR_ACTIVITY_TYPE = "activity_type"
ATTR_CS_ON = "cs_on"
ATTR_CYCLES = "cycles"
ATTR_DELAY = "delay"
ATTR_DELAY_ON = "delay_on"
ATTR_NEXT_RUN = "next_run"
ATTR_SOAK = "soak"
ATTR_STATUS = "status"
ATTR_ZONES = "zones"

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def raise_on_request_error[_T: RainMachineBaseSwitch, **_P](
    func: Callable[Concatenate[_T, _P], Awaitable[None]],
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, None]]:
    """Define a decorator to raise on a request error."""

    async def decorator(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> None:
        """Decorate."""
        try:
            await func(self, *args, **kwargs)
        except RainMachineError as err:
            raise HomeAssistantError(
                f"Error while executing {func.__name__}: {err}",
            ) from err

    return decorator


@dataclass(frozen=True, kw_only=True)
class RainMachineSwitchDescription(
    SwitchEntityDescription, RainMachineEntityDescription
):
    """Describe a RainMachine switch."""


@dataclass(frozen=True, kw_only=True)
class RainMachineActivitySwitchDescription(RainMachineSwitchDescription):
    """Describe a RainMachine activity (program/zone) switch."""

    kind: str
    uid: int


@dataclass(frozen=True, kw_only=True)
class RainMachineRestrictionSwitchDescription(RainMachineSwitchDescription):
    """Describe a RainMachine restriction switch."""

    data_key: str


TYPE_RESTRICTIONS_FREEZE_PROTECT_ENABLED = "freeze_protect_enabled"
TYPE_RESTRICTIONS_HOT_DAYS_EXTRA_WATERING = "hot_days_extra_watering"

RESTRICTIONS_SWITCH_DESCRIPTIONS = (
    RainMachineRestrictionSwitchDescription(
        key=TYPE_RESTRICTIONS_FREEZE_PROTECT_ENABLED,
        translation_key=TYPE_RESTRICTIONS_FREEZE_PROTECT_ENABLED,
        icon="mdi:snowflake-alert",
        api_category=DATA_RESTRICTIONS_UNIVERSAL,
        data_key="freezeProtectEnabled",
    ),
    RainMachineRestrictionSwitchDescription(
        key=TYPE_RESTRICTIONS_HOT_DAYS_EXTRA_WATERING,
        translation_key=TYPE_RESTRICTIONS_HOT_DAYS_EXTRA_WATERING,
        icon="mdi:heat-wave",
        api_category=DATA_RESTRICTIONS_UNIVERSAL,
        data_key="hotDaysExtraWatering",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RainMachineConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up RainMachine switches based on a config entry."""
    platform = entity_platform.async_get_current_platform()

    services: tuple[tuple[str, VolDictType | None, str], ...] = (
        ("start_program", None, "async_start_program"),
        ("stop_program", None, "async_stop_program"),
    )
    for service_name, schema, method in services:
        platform.async_register_entity_service(service_name, schema, method)

    data = entry.runtime_data
    entities: list[RainMachineBaseSwitch] = []

    program_coordinator = data.coordinators[DATA_PROGRAMS]
    for uid, program in program_coordinator.data.items():
        name = program["name"].capitalize()
        entities.extend(
            (
                RainMachineProgram(
                    entry,
                    data,
                    RainMachineActivitySwitchDescription(
                        key=f"program_{uid}",
                        name=f"{name} program",
                        api_category=DATA_PROGRAMS,
                        kind="program",
                        uid=uid,
                    ),
                ),
                RainMachineProgramEnabled(
                    entry,
                    data,
                    RainMachineActivitySwitchDescription(
                        key=f"program_{uid}_enabled",
                        name=f"{name} program enabled",
                        api_category=DATA_PROGRAMS,
                        kind="program",
                        uid=uid,
                    ),
                ),
            )
        )

    zone_coordinator = data.coordinators[DATA_ZONES]
    for uid, zone in zone_coordinator.data.items():
        name = zone["name"].capitalize()
        entities.append(
            RainMachineZoneEnabled(
                entry,
                data,
                RainMachineActivitySwitchDescription(
                    key=f"zone_{uid}_enabled",
                    name=f"{name} enabled",
                    api_category=DATA_ZONES,
                    kind="zone",
                    uid=uid,
                ),
            )
        )

    # Add switches to control restrictions:
    for description in RESTRICTIONS_SWITCH_DESCRIPTIONS:
        coordinator = data.coordinators[description.api_category]
        if not key_exists(coordinator.data, description.data_key):
            continue
        entities.append(RainMachineRestrictionSwitch(entry, data, description))

    async_add_entities(entities)


class RainMachineBaseSwitch(RainMachineEntity, SwitchEntity):
    """Define a base RainMachine switch."""

    entity_description: RainMachineSwitchDescription

    def __init__(
        self,
        entry: ConfigEntry,
        data: RainMachineData,
        description: RainMachineSwitchDescription,
    ) -> None:
        """Initialize."""
        super().__init__(entry, data, description)

        self._attr_is_on = False
        self._entry = entry

    @callback
    def _update_activities(self) -> None:
        """Update all activity data."""
        self.hass.async_create_task(
            async_update_programs_and_zones(self.hass, self._entry)
        )

    async def async_start_program(self) -> None:
        """Execute the start_program entity service."""
        raise NotImplementedError("Service not implemented for this entity")

    async def async_stop_program(self) -> None:
        """Execute the stop_program entity service."""
        raise NotImplementedError("Service not implemented for this entity")


class RainMachineActivitySwitch(RainMachineBaseSwitch):
    """Define a RainMachine switch to start/stop a program."""

    _attr_icon = "mdi:water"
    entity_description: RainMachineActivitySwitchDescription

    def __init__(
        self,
        entry: ConfigEntry,
        data: RainMachineData,
        description: RainMachineSwitchDescription,
    ) -> None:
        """Initialize."""
        super().__init__(entry, data, description)

        self._attr_extra_state_attributes[ATTR_ACTIVITY_TYPE] = (
            self.entity_description.kind
        )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off.

        The only way this could occur is if someone rapidly turns a disabled activity
        off right after turning it on.
        """
        if not self.coordinator.data[self.entity_description.uid]["active"]:
            raise HomeAssistantError(
                f"Cannot turn off an inactive program: {self.name}"
            )

        await self.async_turn_off_when_active(**kwargs)

    @raise_on_request_error
    async def async_turn_off_when_active(self, **kwargs: Any) -> None:
        """Turn the switch off when its associated activity is active."""
        raise NotImplementedError

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        if not self.coordinator.data[self.entity_description.uid]["active"]:
            self._attr_is_on = False
            self.async_write_ha_state()
            raise HomeAssistantError(f"Cannot turn on an inactive program: {self.name}")

        await self.async_turn_on_when_active(**kwargs)

    @raise_on_request_error
    async def async_turn_on_when_active(self, **kwargs: Any) -> None:
        """Turn the switch on when its associated activity is active."""
        raise NotImplementedError


class RainMachineEnabledSwitch(RainMachineBaseSwitch):
    """Define a RainMachine switch to enable/disable an activity (program or zone)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:cog"
    entity_description: RainMachineActivitySwitchDescription

    def __init__(
        self,
        entry: ConfigEntry,
        data: RainMachineData,
        description: RainMachineSwitchDescription,
    ) -> None:
        """Initialize."""
        super().__init__(entry, data, description)

        self._attr_extra_state_attributes[ATTR_ACTIVITY_TYPE] = (
            self.entity_description.kind
        )

    @callback
    @override
    def update_from_latest_data(self) -> None:
        """Update the entity when new data is received."""
        self._attr_is_on = self.coordinator.data[self.entity_description.uid]["active"]


class RainMachineProgram(RainMachineActivitySwitch):
    """Define a RainMachine program."""

    @override
    async def async_start_program(self) -> None:
        """Start the program."""
        await self.async_turn_on()

    @override
    async def async_stop_program(self) -> None:
        """Stop the program."""
        await self.async_turn_off()

    @raise_on_request_error
    @override
    async def async_turn_off_when_active(self, **kwargs: Any) -> None:
        """Turn the switch off when its associated activity is active."""
        await self._data.controller.programs.stop(self.entity_description.uid)
        self._update_activities()

    @raise_on_request_error
    @override
    async def async_turn_on_when_active(self, **kwargs: Any) -> None:
        """Turn the switch on when its associated activity is active."""
        await self._data.controller.programs.start(self.entity_description.uid)
        self._update_activities()

    @callback
    @override
    def update_from_latest_data(self) -> None:
        """Update the entity when new data is received."""
        data = self.coordinator.data[self.entity_description.uid]

        self._attr_is_on = bool(data["status"])

        next_run: str | None
        if data.get("nextRun") is None:
            next_run = None
        else:
            next_run = datetime.strptime(
                f"{data['nextRun']} {data['startTime']}",
                "%Y-%m-%d %H:%M",
            ).isoformat()

        self._attr_extra_state_attributes.update(
            {
                ATTR_ID: self.entity_description.uid,
                ATTR_NEXT_RUN: next_run,
                ATTR_SOAK: data.get("soak"),
                ATTR_STATUS: RUN_STATE_MAP[data["status"]],
                ATTR_ZONES: [z for z in data["wateringTimes"] if z["active"]],
            }
        )


class RainMachineProgramEnabled(RainMachineEnabledSwitch):
    """Define a switch to enable/disable a RainMachine program."""

    @raise_on_request_error
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the program."""
        tasks = [
            self._data.controller.programs.stop(self.entity_description.uid),
            self._data.controller.programs.disable(self.entity_description.uid),
        ]
        await asyncio.gather(*tasks)
        self._update_activities()

    @raise_on_request_error
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the program."""
        await self._data.controller.programs.enable(self.entity_description.uid)
        self._update_activities()


class RainMachineRestrictionSwitch(RainMachineBaseSwitch):
    """Define a RainMachine restriction setting."""

    _attr_entity_category = EntityCategory.CONFIG
    entity_description: RainMachineRestrictionSwitchDescription

    @raise_on_request_error
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the restriction."""
        await self._data.controller.restrictions.set_universal(
            {self.entity_description.data_key: False}
        )
        self._attr_is_on = False
        self.async_write_ha_state()

    @raise_on_request_error
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the restriction."""
        await self._data.controller.restrictions.set_universal(
            {self.entity_description.data_key: True}
        )
        self._attr_is_on = True
        self.async_write_ha_state()

    @callback
    @override
    def update_from_latest_data(self) -> None:
        """Update the entity when new data is received."""
        self._attr_is_on = self.coordinator.data[self.entity_description.data_key]


class RainMachineZoneEnabled(RainMachineEnabledSwitch):
    """Define a switch to enable/disable a RainMachine zone."""

    @raise_on_request_error
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the zone."""
        tasks = [
            self._data.controller.zones.stop(self.entity_description.uid),
            self._data.controller.zones.disable(self.entity_description.uid),
        ]
        await asyncio.gather(*tasks)
        self._update_activities()

    @raise_on_request_error
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the zone."""
        await self._data.controller.zones.enable(self.entity_description.uid)
        self._update_activities()

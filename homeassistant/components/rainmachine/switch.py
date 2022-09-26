"""This component provides support for RainMachine programs and zones."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypeVar

from regenmaschine.errors import RainMachineError
from typing_extensions import Concatenate, ParamSpec
import voluptuous as vol

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RainMachineData, RainMachineEntity, async_update_programs_and_zones
from .const import (
    CONF_ZONE_RUN_TIME,
    DATA_PROGRAMS,
    DATA_RESTRICTIONS_UNIVERSAL,
    DATA_ZONES,
    DEFAULT_ZONE_RUN,
    DOMAIN,
)
from .model import (
    RainMachineEntityDescription,
    RainMachineEntityDescriptionMixinDataKey,
    RainMachineEntityDescriptionMixinUid,
)
from .util import RUN_STATE_MAP

ATTR_AREA = "area"
ATTR_CS_ON = "cs_on"
ATTR_CURRENT_CYCLE = "current_cycle"
ATTR_CYCLES = "cycles"
ATTR_DELAY = "delay"
ATTR_DELAY_ON = "delay_on"
ATTR_FIELD_CAPACITY = "field_capacity"
ATTR_NEXT_RUN = "next_run"
ATTR_NO_CYCLES = "number_of_cycles"
ATTR_PRECIP_RATE = "sprinkler_head_precipitation_rate"
ATTR_RESTRICTIONS = "restrictions"
ATTR_SLOPE = "slope"
ATTR_SOAK = "soak"
ATTR_SOIL_TYPE = "soil_type"
ATTR_SPRINKLER_TYPE = "sprinkler_head_type"
ATTR_STATUS = "status"
ATTR_SUN_EXPOSURE = "sun_exposure"
ATTR_VEGETATION_TYPE = "vegetation_type"
ATTR_ZONES = "zones"

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

SOIL_TYPE_MAP = {
    0: "Not Set",
    1: "Clay Loam",
    2: "Silty Clay",
    3: "Clay",
    4: "Loam",
    5: "Sandy Loam",
    6: "Loamy Sand",
    7: "Sand",
    8: "Sandy Clay",
    9: "Silt Loam",
    10: "Silt",
    99: "Other",
}

SLOPE_TYPE_MAP = {
    0: "Not Set",
    1: "Flat",
    2: "Moderate",
    3: "High",
    4: "Very High",
    99: "Other",
}

SPRINKLER_TYPE_MAP = {
    0: "Not Set",
    1: "Popup Spray",
    2: "Rotors Low Rate",
    3: "Surface Drip",
    4: "Bubblers Drip",
    5: "Rotors High Rate",
    99: "Other",
}

SUN_EXPOSURE_MAP = {0: "Not Set", 1: "Full Sun", 2: "Partial Shade", 3: "Full Shade"}

VEGETATION_MAP = {
    0: "Not Set",
    1: "Not Set",
    2: "Cool Season Grass",
    3: "Fruit Trees",
    4: "Flowers",
    5: "Vegetables",
    6: "Citrus",
    7: "Bushes",
    9: "Drought Tolerant Plants",
    10: "Warm Season Grass",
    11: "Trees",
    99: "Other",
}


_T = TypeVar("_T", bound="RainMachineBaseSwitch")
_P = ParamSpec("_P")


def raise_on_request_error(
    func: Callable[Concatenate[_T, _P], Awaitable[None]]
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


@dataclass
class RainMachineSwitchDescription(
    SwitchEntityDescription,
    RainMachineEntityDescription,
):
    """Describe a RainMachine switch."""


@dataclass
class RainMachineActivitySwitchDescription(
    RainMachineSwitchDescription, RainMachineEntityDescriptionMixinUid
):
    """Describe a RainMachine activity (program/zone) switch."""


@dataclass
class RainMachineRestrictionSwitchDescription(
    RainMachineSwitchDescription, RainMachineEntityDescriptionMixinDataKey
):
    """Describe a RainMachine restriction switch."""


TYPE_RESTRICTIONS_FREEZE_PROTECT_ENABLED = "freeze_protect_enabled"
TYPE_RESTRICTIONS_HOT_DAYS_EXTRA_WATERING = "hot_days_extra_watering"

RESTRICTIONS_SWITCH_DESCRIPTIONS = (
    RainMachineRestrictionSwitchDescription(
        key=TYPE_RESTRICTIONS_FREEZE_PROTECT_ENABLED,
        name="Freeze protection",
        icon="mdi:snowflake-alert",
        api_category=DATA_RESTRICTIONS_UNIVERSAL,
        data_key="freezeProtectEnabled",
    ),
    RainMachineRestrictionSwitchDescription(
        key=TYPE_RESTRICTIONS_HOT_DAYS_EXTRA_WATERING,
        name="Extra water on hot days",
        icon="mdi:heat-wave",
        api_category=DATA_RESTRICTIONS_UNIVERSAL,
        data_key="hotDaysExtraWatering",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up RainMachine switches based on a config entry."""
    platform = entity_platform.async_get_current_platform()

    for service_name, schema, method in (
        ("start_program", {}, "async_start_program"),
        (
            "start_zone",
            {
                vol.Optional(
                    CONF_ZONE_RUN_TIME, default=DEFAULT_ZONE_RUN
                ): cv.positive_int
            },
            "async_start_zone",
        ),
        ("stop_program", {}, "async_stop_program"),
        ("stop_zone", {}, "async_stop_zone"),
    ):
        platform.async_register_entity_service(service_name, schema, method)

    data: RainMachineData = hass.data[DOMAIN][entry.entry_id]
    entities: list[RainMachineBaseSwitch] = []

    for kind, api_category, switch_class, switch_enabled_class in (
        ("program", DATA_PROGRAMS, RainMachineProgram, RainMachineProgramEnabled),
        ("zone", DATA_ZONES, RainMachineZone, RainMachineZoneEnabled),
    ):
        coordinator = data.coordinators[api_category]
        for uid, activity in coordinator.data.items():
            name = activity["name"].capitalize()

            # Add a switch to start/stop the program or zone:
            entities.append(
                switch_class(
                    entry,
                    data,
                    RainMachineActivitySwitchDescription(
                        key=f"{kind}_{uid}",
                        name=name,
                        api_category=api_category,
                        uid=uid,
                    ),
                )
            )

            # Add a switch to enabled/disable the program or zone:
            entities.append(
                switch_enabled_class(
                    entry,
                    data,
                    RainMachineActivitySwitchDescription(
                        key=f"{kind}_{uid}_enabled",
                        name=f"{name} enabled",
                        api_category=api_category,
                        uid=uid,
                    ),
                )
            )

    # Add switches to control restrictions:
    for description in RESTRICTIONS_SWITCH_DESCRIPTIONS:
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

    async def async_start_zone(self, *, zone_run_time: int) -> None:
        """Execute the start_zone entity service."""
        raise NotImplementedError("Service not implemented for this entity")

    async def async_stop_program(self) -> None:
        """Execute the stop_program entity service."""
        raise NotImplementedError("Service not implemented for this entity")

    async def async_stop_zone(self) -> None:
        """Execute the stop_zone entity service."""
        raise NotImplementedError("Service not implemented for this entity")


class RainMachineActivitySwitch(RainMachineBaseSwitch):
    """Define a RainMachine switch to start/stop an activity (program or zone)."""

    _attr_icon = "mdi:water"
    entity_description: RainMachineActivitySwitchDescription

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off.

        The only way this could occur is if someone rapidly turns a disabled activity
        off right after turning it on.
        """
        if not self.coordinator.data[self.entity_description.uid]["active"]:
            raise HomeAssistantError(
                f"Cannot turn off an inactive program/zone: {self.name}"
            )

        await self.async_turn_off_when_active(**kwargs)

    @raise_on_request_error
    async def async_turn_off_when_active(self, **kwargs: Any) -> None:
        """Turn the switch off when its associated activity is active."""
        raise NotImplementedError

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        if not self.coordinator.data[self.entity_description.uid]["active"]:
            self._attr_is_on = False
            self.async_write_ha_state()
            raise HomeAssistantError(
                f"Cannot turn on an inactive program/zone: {self.name}"
            )

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

    @callback
    def update_from_latest_data(self) -> None:
        """Update the entity when new data is received."""
        self._attr_is_on = self.coordinator.data[self.entity_description.uid]["active"]


class RainMachineProgram(RainMachineActivitySwitch):
    """Define a RainMachine program."""

    async def async_start_program(self) -> None:
        """Start the program."""
        await self.async_turn_on()

    async def async_stop_program(self) -> None:
        """Stop the program."""
        await self.async_turn_off()

    @raise_on_request_error
    async def async_turn_off_when_active(self, **kwargs: Any) -> None:
        """Turn the switch off when its associated activity is active."""
        await self._data.controller.programs.stop(self.entity_description.uid)
        self._update_activities()

    @raise_on_request_error
    async def async_turn_on_when_active(self, **kwargs: Any) -> None:
        """Turn the switch on when its associated activity is active."""
        await self._data.controller.programs.start(self.entity_description.uid)
        self._update_activities()

    @callback
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
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the program."""
        tasks = [
            self._data.controller.programs.stop(self.entity_description.uid),
            self._data.controller.programs.disable(self.entity_description.uid),
        ]
        await asyncio.gather(*tasks)
        self._update_activities()

    @raise_on_request_error
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the program."""
        await self._data.controller.programs.enable(self.entity_description.uid)
        self._update_activities()


class RainMachineRestrictionSwitch(RainMachineBaseSwitch):
    """Define a RainMachine restriction setting."""

    _attr_entity_category = EntityCategory.CONFIG
    entity_description: RainMachineRestrictionSwitchDescription

    @raise_on_request_error
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the restriction."""
        await self._data.controller.restrictions.set_universal(
            {self.entity_description.data_key: False}
        )
        self._attr_is_on = False
        self.async_write_ha_state()

    @raise_on_request_error
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the restriction."""
        await self._data.controller.restrictions.set_universal(
            {self.entity_description.data_key: True}
        )
        self._attr_is_on = True
        self.async_write_ha_state()

    @callback
    def update_from_latest_data(self) -> None:
        """Update the entity when new data is received."""
        self._attr_is_on = self.coordinator.data[self.entity_description.data_key]


class RainMachineZone(RainMachineActivitySwitch):
    """Define a RainMachine zone."""

    async def async_start_zone(self, *, zone_run_time: int) -> None:
        """Start a particular zone for a certain amount of time."""
        await self.async_turn_on(duration=zone_run_time)

    async def async_stop_zone(self) -> None:
        """Stop a zone."""
        await self.async_turn_off()

    @raise_on_request_error
    async def async_turn_off_when_active(self, **kwargs: Any) -> None:
        """Turn the switch off when its associated activity is active."""
        await self._data.controller.zones.stop(self.entity_description.uid)
        self._update_activities()

    @raise_on_request_error
    async def async_turn_on_when_active(self, **kwargs: Any) -> None:
        """Turn the switch on when its associated activity is active."""
        await self._data.controller.zones.start(
            self.entity_description.uid,
            kwargs.get("duration", self._entry.options[CONF_ZONE_RUN_TIME]),
        )
        self._update_activities()

    @callback
    def update_from_latest_data(self) -> None:
        """Update the entity when new data is received."""
        data = self.coordinator.data[self.entity_description.uid]

        self._attr_is_on = bool(data["state"])

        attrs = {
            ATTR_CURRENT_CYCLE: data["cycle"],
            ATTR_ID: data["uid"],
            ATTR_NO_CYCLES: data["noOfCycles"],
            ATTR_RESTRICTIONS: data["restriction"],
            ATTR_SLOPE: SLOPE_TYPE_MAP.get(data["slope"], 99),
            ATTR_SOIL_TYPE: SOIL_TYPE_MAP.get(data["soil"], 99),
            ATTR_SPRINKLER_TYPE: SPRINKLER_TYPE_MAP.get(data["group_id"], 99),
            ATTR_STATUS: RUN_STATE_MAP[data["state"]],
            ATTR_SUN_EXPOSURE: SUN_EXPOSURE_MAP.get(data.get("sun")),
            ATTR_VEGETATION_TYPE: VEGETATION_MAP.get(data["type"], 99),
        }

        if "waterSense" in data:
            if "area" in data["waterSense"]:
                attrs[ATTR_AREA] = round(data["waterSense"]["area"], 2)
            if "fieldCapacity" in data["waterSense"]:
                attrs[ATTR_FIELD_CAPACITY] = round(
                    data["waterSense"]["fieldCapacity"], 2
                )
            if "precipitationRate" in data["waterSense"]:
                attrs[ATTR_PRECIP_RATE] = round(
                    data["waterSense"]["precipitationRate"], 2
                )

        self._attr_extra_state_attributes.update(attrs)


class RainMachineZoneEnabled(RainMachineEnabledSwitch):
    """Define a switch to enable/disable a RainMachine zone."""

    @raise_on_request_error
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the zone."""
        tasks = [
            self._data.controller.zones.stop(self.entity_description.uid),
            self._data.controller.zones.disable(self.entity_description.uid),
        ]
        await asyncio.gather(*tasks)
        self._update_activities()

    @raise_on_request_error
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the zone."""
        await self._data.controller.zones.enable(self.entity_description.uid)
        self._update_activities()

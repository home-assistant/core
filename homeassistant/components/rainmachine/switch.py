"""This component provides support for RainMachine programs and zones."""
from __future__ import annotations

from collections.abc import Coroutine
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from regenmaschine.controller import Controller
from regenmaschine.errors import RequestError
import voluptuous as vol

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ID, ENTITY_CATEGORY_CONFIG
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import RainMachineEntity, async_update_programs_and_zones
from .const import (
    CONF_ZONE_RUN_TIME,
    DATA_CONTROLLER,
    DATA_COORDINATOR,
    DATA_PROGRAMS,
    DATA_ZONES,
    DEFAULT_ZONE_RUN,
    DOMAIN,
    LOGGER,
)

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
ATTR_TIME_REMAINING = "time_remaining"
ATTR_VEGETATION_TYPE = "vegetation_type"
ATTR_ZONES = "zones"

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

RUN_STATUS_MAP = {0: "Not Running", 1: "Running", 2: "Queued"}

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


@dataclass
class RainMachineSwitchDescriptionMixin:
    """Define an entity description mixin for switches."""

    uid: int


@dataclass
class RainMachineSwitchDescription(
    SwitchEntityDescription, RainMachineSwitchDescriptionMixin
):
    """Describe a RainMachine switch."""


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

    data = hass.data[DOMAIN][entry.entry_id]
    controller = data[DATA_CONTROLLER]
    program_coordinator = data[DATA_COORDINATOR][DATA_PROGRAMS]
    zone_coordinator = data[DATA_COORDINATOR][DATA_ZONES]

    entities: list[RainMachineProgram | RainMachineZone] = []

    for kind, coordinator, switch_class, switch_enabled_class in [
        ("program", program_coordinator, RainMachineProgram, RainMachineProgramEnabled),
        ("zone", zone_coordinator, RainMachineZone, RainMachineZoneEnabled),
    ]:
        for uid, data in coordinator.data.items():
            entities.append(
                switch_class(
                    entry,
                    coordinator,
                    controller,
                    RainMachineSwitchDescription(
                        key=f"{controller.name}_{kind}_{uid}",
                        name=data["name"],
                        uid=uid,
                    ),
                )
            )
            entities.append(
                switch_enabled_class(
                    entry,
                    coordinator,
                    controller,
                    RainMachineSwitchDescription(
                        key=f"{controller.name}_{kind}_{uid}_enabled",
                        name=f"{data['name']} Enabled",
                        entity_category=ENTITY_CATEGORY_CONFIG,
                        uid=uid,
                    ),
                )
            )

    async_add_entities(entities)


class RainMachineSwitch(RainMachineEntity, SwitchEntity):
    """Define a base RainMachine switch."""

    _attr_icon = "mdi:water"
    entity_description: RainMachineSwitchDescription

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        controller: Controller,
        description: RainMachineSwitchDescription,
    ) -> None:
        """Initialize."""
        super().__init__(entry, coordinator, controller, description)

        self._attr_is_on = False
        self._data = coordinator.data[description.uid]
        self._entry = entry

    async def _async_run_api_coroutine(self, api_coro: Coroutine) -> None:
        """Await an API coroutine, handle any errors, and update as appropriate."""
        try:
            resp = await api_coro
        except RequestError as err:
            LOGGER.error(
                'Error while executing %s on "%s": %s',
                api_coro.__name__,
                self.name,
                err,
            )
            return

        if resp["statusCode"] != 0:
            LOGGER.error(
                'Error while executing %s on "%s": %s',
                api_coro.__name__,
                self.name,
                resp["message"],
            )
            return

        # Because of how inextricably linked programs and zones are, anytime one is
        # toggled, we make sure to update the data of both coordinators:
        self.hass.async_create_task(
            async_update_programs_and_zones(self.hass, self._entry)
        )

    async def async_start_program(self) -> None:
        """Start the program."""
        raise NotImplementedError("Service not implemented for this entity")

    async def async_start_zone(self, *, zone_run_time: int) -> None:
        """Start the zone."""
        raise NotImplementedError("Service not implemented for this entity")

    async def async_stop_program(self) -> None:
        """Stop the program."""
        raise NotImplementedError("Service not implemented for this entity")

    async def async_stop_zone(self) -> None:
        """Stop the zone."""
        raise NotImplementedError("Service not implemented for this entity")


class RainMachineProgram(RainMachineSwitch):
    """Define a RainMachine program."""

    async def async_start_program(self) -> None:
        """Start the program."""
        await self.async_turn_on()

    async def async_stop_program(self) -> None:
        """Stop the program."""
        await self.async_turn_off()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_run_api_coroutine(
            self._controller.programs.stop(self.entity_description.uid)
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_run_api_coroutine(
            self._controller.programs.start(self.entity_description.uid)
        )

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        self._data = self.coordinator.data[self.entity_description.uid]

        self._attr_is_on = bool(self._data["status"])

        next_run: str | None
        if self._data.get("nextRun") is None:
            next_run = None
        else:
            next_run = datetime.strptime(
                f"{self._data['nextRun']} {self._data['startTime']}",
                "%Y-%m-%d %H:%M",
            ).isoformat()

        self._attr_extra_state_attributes.update(
            {
                ATTR_ID: self.entity_description.uid,
                ATTR_NEXT_RUN: next_run,
                ATTR_SOAK: self._data.get("soak"),
                ATTR_STATUS: RUN_STATUS_MAP[self._data["status"]],
                ATTR_ZONES: [z for z in self._data["wateringTimes"] if z["active"]],
            }
        )


class RainMachineProgramEnabled(RainMachineSwitch):
    """Define a switch to enable/disable a RainMachine program."""

    _attr_icon = "mdi:cog"

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the program."""
        await self._async_run_api_coroutine(
            self._controller.programs.disable(self.entity_description.uid)
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the program."""
        await self._async_run_api_coroutine(
            self._controller.programs.enable(self.entity_description.uid)
        )


class RainMachineZone(RainMachineSwitch):
    """Define a RainMachine zone."""

    async def async_start_zone(self, *, zone_run_time: int) -> None:
        """Start a particular zone for a certain amount of time."""
        await self.async_turn_off(duration=zone_run_time)

    async def async_stop_zone(self) -> None:
        """Stop a zone."""
        await self.async_turn_off()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the zone off."""
        await self._async_run_api_coroutine(
            self._controller.zones.stop(self.entity_description.uid)
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the zone on."""
        await self._async_run_api_coroutine(
            self._controller.zones.start(
                self.entity_description.uid,
                kwargs.get("duration", self._entry.options[CONF_ZONE_RUN_TIME]),
            )
        )

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        self._data = self.coordinator.data[self.entity_description.uid]

        self._attr_is_on = bool(self._data["state"])

        self._attr_extra_state_attributes.update(
            {
                ATTR_AREA: self._data.get("waterSense").get("area"),
                ATTR_CURRENT_CYCLE: self._data.get("cycle"),
                ATTR_FIELD_CAPACITY: self._data.get("waterSense").get("fieldCapacity"),
                ATTR_ID: self._data["uid"],
                ATTR_NO_CYCLES: self._data.get("noOfCycles"),
                ATTR_PRECIP_RATE: self._data.get("waterSense").get("precipitationRate"),
                ATTR_RESTRICTIONS: self._data.get("restriction"),
                ATTR_SLOPE: SLOPE_TYPE_MAP.get(self._data.get("slope")),
                ATTR_SOIL_TYPE: SOIL_TYPE_MAP.get(self._data.get("soil")),
                ATTR_SPRINKLER_TYPE: SPRINKLER_TYPE_MAP.get(self._data.get("group_id")),
                ATTR_STATUS: RUN_STATUS_MAP[self._data["state"]],
                ATTR_SUN_EXPOSURE: SUN_EXPOSURE_MAP.get(self._data.get("sun")),
                ATTR_TIME_REMAINING: self._data.get("remaining"),
                ATTR_VEGETATION_TYPE: VEGETATION_MAP.get(self._data.get("type")),
            }
        )


class RainMachineZoneEnabled(RainMachineSwitch):
    """Define a switch to enable/disable a RainMachine zone."""

    _attr_icon = "mdi:cog"

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the zone."""
        await self._async_run_api_coroutine(
            self._controller.zones.disable(self.entity_description.uid)
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the zone."""
        await self._async_run_api_coroutine(
            self._controller.zones.enable(self.entity_description.uid)
        )

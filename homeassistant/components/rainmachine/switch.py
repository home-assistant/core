"""This component provides support for RainMachine programs and zones."""
from datetime import datetime
from typing import Callable, Coroutine

from regenmaschine.controller import Controller
from regenmaschine.errors import RequestError

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import RainMachineEntity, async_update_programs_and_zones
from .const import (
    CONF_ZONE_RUN_TIME,
    DATA_CONTROLLER,
    DATA_COORDINATOR,
    DATA_PROGRAMS,
    DATA_ZONES,
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
    2: "Rotors",
    3: "Surface Drip",
    4: "Bubblers Drip",
    99: "Other",
}

SUN_EXPOSURE_MAP = {0: "Not Set", 1: "Full Sun", 2: "Partial Shade", 3: "Full Shade"}

VEGETATION_MAP = {
    0: "Not Set",
    2: "Cool Season Grass",
    3: "Fruit Trees",
    4: "Flowers",
    5: "Vegetables",
    6: "Citrus",
    7: "Trees and Bushes",
    9: "Drought Tolerant Plants",
    10: "Warm Season Grass",
    99: "Other",
}

SWITCH_TYPE_PROGRAM = "program"
SWITCH_TYPE_ZONE = "zone"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up RainMachine switches based on a config entry."""
    controller = hass.data[DOMAIN][DATA_CONTROLLER][entry.entry_id]
    programs_coordinator = hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id][
        DATA_PROGRAMS
    ]
    zones_coordinator = hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id][DATA_ZONES]

    entities = []
    for uid, program in programs_coordinator.data.items():
        entities.append(
            RainMachineProgram(
                programs_coordinator, controller, uid, program["name"], entry
            )
        )
    for uid, zone in zones_coordinator.data.items():
        entities.append(
            RainMachineZone(zones_coordinator, controller, uid, zone["name"], entry)
        )

    async_add_entities(entities)


class RainMachineSwitch(RainMachineEntity, SwitchEntity):
    """A class to represent a generic RainMachine switch."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        controller: Controller,
        uid: int,
        name: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize a generic RainMachine switch."""
        super().__init__(coordinator, controller)
        self._data = coordinator.data[uid]
        self._entry = entry
        self._is_active = True
        self._is_on = False
        self._name = name
        self._switch_type = type(self).__name__
        self._uid = uid

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._is_active and self.coordinator.last_update_success

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:water"

    @property
    def is_on(self) -> bool:
        """Return whether the program is running."""
        return self._is_on

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._unique_id}_{self._switch_type}_{self._uid}"

    async def _async_run_switch_coroutine(self, api_coro: Coroutine) -> None:
        """Run a coroutine to toggle the switch."""
        try:
            resp = await api_coro
        except RequestError as err:
            LOGGER.error(
                'Error while toggling %s "%s": %s',
                self._switch_type,
                self.unique_id,
                err,
            )
            return

        if resp["statusCode"] != 0:
            LOGGER.error(
                'Error while toggling %s "%s": %s',
                self._switch_type,
                self.unique_id,
                resp["message"],
            )
            return

        # Because of how inextricably linked programs and zones are, anytime one is
        # toggled, we make sure to update the data of both coordinators:
        self.hass.async_create_task(
            async_update_programs_and_zones(self.hass, self._entry)
        )

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        self._data = self.coordinator.data[self._uid]
        self._is_active = self._data["active"]


class RainMachineProgram(RainMachineSwitch):
    """A RainMachine program."""

    @property
    def zones(self) -> list:
        """Return a list of active zones associated with this program."""
        return [z for z in self._data["wateringTimes"] if z["active"]]

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the program off."""
        await self._async_run_switch_coroutine(
            self._controller.programs.stop(self._uid)
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the program on."""
        await self._async_run_switch_coroutine(
            self._controller.programs.start(self._uid)
        )

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        super().update_from_latest_data()

        self._is_on = bool(self._data["status"])

        if self._data.get("nextRun") is not None:
            next_run = datetime.strptime(
                f"{self._data['nextRun']} {self._data['startTime']}",
                "%Y-%m-%d %H:%M",
            ).isoformat()
        else:
            next_run = None

        self._attrs.update(
            {
                ATTR_ID: self._uid,
                ATTR_NEXT_RUN: next_run,
                ATTR_SOAK: self.coordinator.data[self._uid].get("soak"),
                ATTR_STATUS: RUN_STATUS_MAP[self.coordinator.data[self._uid]["status"]],
                ATTR_ZONES: ", ".join(z["name"] for z in self.zones),
            }
        )


class RainMachineZone(RainMachineSwitch):
    """A RainMachine zone."""

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the zone off."""
        await self._async_run_switch_coroutine(self._controller.zones.stop(self._uid))

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the zone on."""
        await self._async_run_switch_coroutine(
            self._controller.zones.start(
                self._uid,
                self._entry.options[CONF_ZONE_RUN_TIME],
            )
        )

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        super().update_from_latest_data()

        self._is_on = bool(self._data["state"])

        self._attrs.update(
            {
                ATTR_STATUS: RUN_STATUS_MAP[self._data["state"]],
                ATTR_AREA: self._data.get("waterSense").get("area"),
                ATTR_CURRENT_CYCLE: self._data.get("cycle"),
                ATTR_FIELD_CAPACITY: self._data.get("waterSense").get("fieldCapacity"),
                ATTR_ID: self._data["uid"],
                ATTR_NO_CYCLES: self._data.get("noOfCycles"),
                ATTR_PRECIP_RATE: self._data.get("waterSense").get("precipitationRate"),
                ATTR_RESTRICTIONS: self._data.get("restriction"),
                ATTR_SLOPE: SLOPE_TYPE_MAP.get(self._data.get("slope")),
                ATTR_SOIL_TYPE: SOIL_TYPE_MAP.get(self._data.get("sun")),
                ATTR_SPRINKLER_TYPE: SPRINKLER_TYPE_MAP.get(self._data.get("group_id")),
                ATTR_SUN_EXPOSURE: SUN_EXPOSURE_MAP.get(self._data.get("sun")),
                ATTR_TIME_REMAINING: self._data.get("remaining"),
                ATTR_VEGETATION_TYPE: VEGETATION_MAP.get(self._data.get("type")),
            }
        )

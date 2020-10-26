"""This component provides support for RainMachine programs and zones."""
from datetime import datetime

from regenmaschine.errors import RequestError

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import ATTR_ID
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import RainMachineEntity, async_update_programs_and_zones
from .const import (
    CONF_ZONE_RUN_TIME,
    DATA_CONTROLLER,
    DATA_PROGRAMS,
    DATA_ZONES,
    DATA_ZONES_DETAILS,
    DOMAIN,
    LOGGER,
    PROGRAM_UPDATE_TOPIC,
    ZONE_UPDATE_TOPIC,
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


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up RainMachine switches based on a config entry."""
    controller = hass.data[DOMAIN][DATA_CONTROLLER][entry.entry_id]

    programs_coordinator = hass.data[DOMAIN][DATA_CONTROLLER][entry.entry_id][
        DATA_PROGRAMS
    ]
    zones_coordinator = hass.data[DOMAIN][DATA_CONTROLLER][entry.entry_id][DATA_ZONES]

    entities = []
    for program in programs_coordinator.data:
        entities.append(RainMachineProgram(programs_coordinator, controller))
    for zone in zones_coordinator.data:
        entities.append(RainMachineZone(zones_coordinator, controller))

    async_add_entities(entities)


class RainMachineSwitch(RainMachineEntity, SwitchEntity):
    """A class to represent a generic RainMachine switch."""

    def __init__(self, rainmachine, switch_data):
        """Initialize a generic RainMachine switch."""
        super().__init__(rainmachine)
        self._is_on = False
        self._name = switch_data["name"]
        self._switch_data = switch_data
        self._rainmachine_entity_id = switch_data["uid"]
        self._switch_type = None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._switch_data["active"]

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
        return "{}_{}_{}".format(
            self.rainmachine.device_mac.replace(":", ""),
            self._switch_type,
            self._rainmachine_entity_id,
        )

    async def _async_run_switch_coroutine(self, api_coro) -> None:
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

        self.hass.async_create_task(
            async_update_programs_and_zones(self.hass, self._config_entry)
        )


class RainMachineProgram(RainMachineSwitch):
    """A RainMachine program."""

    def __init__(self, rainmachine, switch_data):
        """Initialize a generic RainMachine switch."""
        super().__init__(rainmachine, switch_data)
        self._switch_type = SWITCH_TYPE_PROGRAM

    @property
    def zones(self) -> list:
        """Return a list of active zones associated with this program."""
        return [z for z in self._switch_data["wateringTimes"] if z["active"]]

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, PROGRAM_UPDATE_TOPIC, self._update_state
            )
        )

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the program off."""
        await self._async_run_switch_coroutine(
            self.rainmachine.controller.programs.stop(self._rainmachine_entity_id)
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the program on."""
        await self._async_run_switch_coroutine(
            self.rainmachine.controller.programs.start(self._rainmachine_entity_id)
        )

    @callback
    def update_from_latest_data(self) -> None:
        """Update info for the program."""
        [self._switch_data] = [
            p
            for p in self.rainmachine.data[DATA_PROGRAMS]
            if p["uid"] == self._rainmachine_entity_id
        ]

        self._is_on = bool(self._switch_data["status"])

        try:
            next_run = datetime.strptime(
                "{} {}".format(
                    self._switch_data["nextRun"], self._switch_data["startTime"]
                ),
                "%Y-%m-%d %H:%M",
            ).isoformat()
        except ValueError:
            next_run = None

        self._attrs.update(
            {
                ATTR_ID: self._switch_data["uid"],
                ATTR_NEXT_RUN: next_run,
                ATTR_SOAK: self._switch_data.get("soak"),
                ATTR_STATUS: RUN_STATUS_MAP[self._switch_data["status"]],
                ATTR_ZONES: ", ".join(z["name"] for z in self.zones),
            }
        )


class RainMachineZone(RainMachineSwitch):
    """A RainMachine zone."""

    def __init__(self, rainmachine, switch_data):
        """Initialize a RainMachine zone."""
        super().__init__(rainmachine, switch_data)
        self._switch_type = SWITCH_TYPE_ZONE

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, PROGRAM_UPDATE_TOPIC, self._update_state
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(self.hass, ZONE_UPDATE_TOPIC, self._update_state)
        )

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the zone off."""
        await self._async_run_switch_coroutine(
            self.rainmachine.controller.zones.stop(self._rainmachine_entity_id)
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the zone on."""
        await self._async_run_switch_coroutine(
            self.rainmachine.controller.zones.start(
                self._rainmachine_entity_id,
                self.rainmachine.config_entry.options[CONF_ZONE_RUN_TIME],
            )
        )

    @callback
    def update_from_latest_data(self) -> None:
        """Update info for the zone."""
        [self._switch_data] = [
            z
            for z in self.rainmachine.data[DATA_ZONES]
            if z["uid"] == self._rainmachine_entity_id
        ]
        [details] = [
            z
            for z in self.rainmachine.data[DATA_ZONES_DETAILS]
            if z["uid"] == self._rainmachine_entity_id
        ]

        self._is_on = bool(self._switch_data["state"])

        self._attrs.update(
            {
                ATTR_STATUS: RUN_STATUS_MAP[self._switch_data["state"]],
                ATTR_AREA: details.get("waterSense").get("area"),
                ATTR_CURRENT_CYCLE: self._switch_data.get("cycle"),
                ATTR_FIELD_CAPACITY: details.get("waterSense").get("fieldCapacity"),
                ATTR_ID: self._switch_data["uid"],
                ATTR_NO_CYCLES: self._switch_data.get("noOfCycles"),
                ATTR_PRECIP_RATE: details.get("waterSense").get("precipitationRate"),
                ATTR_RESTRICTIONS: self._switch_data.get("restriction"),
                ATTR_SLOPE: SLOPE_TYPE_MAP.get(details.get("slope")),
                ATTR_SOIL_TYPE: SOIL_TYPE_MAP.get(details.get("sun")),
                ATTR_SPRINKLER_TYPE: SPRINKLER_TYPE_MAP.get(details.get("group_id")),
                ATTR_SUN_EXPOSURE: SUN_EXPOSURE_MAP.get(details.get("sun")),
                ATTR_TIME_REMAINING: self._switch_data.get("remaining"),
                ATTR_VEGETATION_TYPE: VEGETATION_MAP.get(self._switch_data.get("type")),
            }
        )

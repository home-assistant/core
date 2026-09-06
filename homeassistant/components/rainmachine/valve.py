"""Valve platform for RainMachine irrigation zones."""

from dataclasses import dataclass
from typing import override

from regenmaschine.errors import RainMachineError
import voluptuous as vol

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityDescription,
    ValveEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RainMachineConfigEntry, RainMachineData
from .const import (
    CONF_ALLOW_INACTIVE_ZONES_TO_RUN,
    CONF_DEFAULT_ZONE_RUN_TIME,
    CONF_USE_APP_RUN_TIMES,
    DATA_PROVISION_SETTINGS,
    DATA_ZONES,
    DEFAULT_ZONE_RUN,
)
from .entity import RainMachineEntity, RainMachineEntityDescription
from .services import async_update_programs_and_zones
from .util import RUN_STATE_MAP

ATTR_AREA = "area"
ATTR_CURRENT_CYCLE = "current_cycle"
ATTR_FIELD_CAPACITY = "field_capacity"
ATTR_NO_CYCLES = "number_of_cycles"
ATTR_PRECIP_RATE = "sprinkler_head_precipitation_rate"
ATTR_RESTRICTIONS = "restrictions"
ATTR_SLOPE = "slope"
ATTR_SOIL_TYPE = "soil_type"
ATTR_SPRINKLER_TYPE = "sprinkler_head_type"
ATTR_STATUS = "status"
ATTR_SUN_EXPOSURE = "sun_exposure"
ATTR_VEGETATION_TYPE = "vegetation_type"
ATTR_ZONE_RUN_TIME = "zone_run_time_from_app"

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


@dataclass(frozen=True, kw_only=True)
class RainMachineValveDescription(ValveEntityDescription, RainMachineEntityDescription):
    """Describe a RainMachine irrigation-zone valve."""

    uid: int


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RainMachineConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up RainMachine irrigation zones as water valves."""
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "start_zone",
        {
            vol.Optional(
                CONF_DEFAULT_ZONE_RUN_TIME, default=DEFAULT_ZONE_RUN
            ): cv.positive_int
        },
        "async_start_zone",
    )
    platform.async_register_entity_service("stop_zone", None, "async_stop_zone")

    data = entry.runtime_data
    coordinator = data.coordinators[DATA_ZONES]
    async_add_entities(
        RainMachineZoneValve(
            entry,
            data,
            RainMachineValveDescription(
                key=f"zone_{uid}",
                name=zone["name"].capitalize(),
                api_category=DATA_ZONES,
                device_class=ValveDeviceClass.WATER,
                uid=uid,
            ),
        )
        for uid, zone in coordinator.data.items()
    )


class RainMachineZoneValve(RainMachineEntity, ValveEntity):
    """Represent a RainMachine irrigation zone as a water valve."""

    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
    _attr_reports_position = False
    entity_description: RainMachineValveDescription

    def __init__(
        self,
        entry: ConfigEntry,
        data: RainMachineData,
        description: RainMachineValveDescription,
    ) -> None:
        """Initialize a RainMachine irrigation-zone valve."""
        super().__init__(entry, data, description)
        self._entry = entry

    @callback
    def _update_activities(self) -> None:
        """Refresh linked program and zone state."""
        self.hass.async_create_task(
            async_update_programs_and_zones(self.hass, self._entry)
        )

    def _ensure_zone_can_run(self) -> None:
        """Reject opening a disabled RainMachine zone unless explicitly allowed."""
        if (
            not self._entry.options[CONF_ALLOW_INACTIVE_ZONES_TO_RUN]
            and not self.coordinator.data[self.entity_description.uid]["active"]
        ):
            raise HomeAssistantError(f"Cannot open an inactive zone: {self.name}")

    def _default_duration(self) -> int:
        """Return the configured run time for this zone."""
        if (
            self._entry.options[CONF_USE_APP_RUN_TIMES]
            and ATTR_ZONE_RUN_TIME in self._attr_extra_state_attributes
        ):
            return int(self._attr_extra_state_attributes[ATTR_ZONE_RUN_TIME])
        return int(self._entry.options[CONF_DEFAULT_ZONE_RUN_TIME])

    async def _async_open(self, duration: int) -> None:
        """Open the zone for a specific number of seconds."""
        self._ensure_zone_can_run()
        try:
            await self._data.controller.zones.start(
                self.entity_description.uid, duration
            )
        except RainMachineError as err:
            raise HomeAssistantError(f"Error while opening {self.name}: {err}") from err
        self._update_activities()

    @override
    async def async_open_valve(self) -> None:
        """Open the irrigation zone using its configured run time."""
        await self._async_open(self._default_duration())

    @override
    async def async_close_valve(self) -> None:
        """Close the irrigation zone."""
        try:
            await self._data.controller.zones.stop(self.entity_description.uid)
        except RainMachineError as err:
            raise HomeAssistantError(f"Error while closing {self.name}: {err}") from err
        self._update_activities()

    async def async_start_zone(self, *, zone_run_time: int) -> None:
        """Start the zone for an explicit duration."""
        await self._async_open(zone_run_time)

    async def async_stop_zone(self) -> None:
        """Stop the zone."""
        await self.async_close_valve()

    @callback
    @override
    def update_from_latest_data(self) -> None:
        """Update the valve state and RainMachine zone attributes."""
        data = self.coordinator.data[self.entity_description.uid]
        self._attr_is_closed = not bool(data["state"])

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

        if self._entry.options[CONF_USE_APP_RUN_TIMES]:
            provision_data = self._data.coordinators[DATA_PROVISION_SETTINGS].data
            if zone_durations := provision_data.get("system", {}).get("zoneDuration"):
                attrs[ATTR_ZONE_RUN_TIME] = zone_durations[
                    list(self.coordinator.data).index(self.entity_description.uid)
                ]

        self._attr_extra_state_attributes.update(attrs)

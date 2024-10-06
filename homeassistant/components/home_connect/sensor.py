"""Provides a sensor for Home Connect."""

import contextlib
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import cast

from homeconnect.api import HomeConnectError

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .api import ConfigEntryAuth
from .const import (
    ATTR_VALUE,
    BSH_OPERATION_STATE,
    BSH_OPERATION_STATE_FINISHED,
    BSH_OPERATION_STATE_PAUSE,
    BSH_OPERATION_STATE_RUN,
    COFFEE_EVENT_BEAN_CONTAINER_EMPTY,
    COFFEE_EVENT_DRIP_TRAY_FULL,
    COFFEE_EVENT_WATER_TANK_EMPTY,
    DOMAIN,
    REFRIGERATION_EVENT_DOOR_ALARM_FREEZER,
    REFRIGERATION_EVENT_DOOR_ALARM_REFRIGERATOR,
    REFRIGERATION_EVENT_TEMP_ALARM_FREEZER,
)
from .entity import HomeConnectEntity, HomeConnectEntityDescription

_LOGGER = logging.getLogger(__name__)


EVENT_OPTIONS = ["Confirmed", "Off", "Present"]


@dataclass(frozen=True, kw_only=True)
class HomeConnectSensorEntityDescription(
    SensorEntityDescription, HomeConnectEntityDescription
):
    """Entity Description class for sensors."""

    default_value: str | None = None
    appliance_types: tuple[str, ...] | None = None
    sign: int = 1


BSH_PROGRAM_SENSORS = (
    HomeConnectSensorEntityDescription(
        key="BSH.Common.Option.RemainingProgramTime",
        device_class=SensorDeviceClass.TIMESTAMP,
        sign=1,
        desc="Program finish time",
    ),
    HomeConnectSensorEntityDescription(
        key="BSH.Common.Option.Duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        sign=1,
    ),
    HomeConnectSensorEntityDescription(
        key="BSH.Common.Option.ProgramProgress",
        native_unit_of_measurement=PERCENTAGE,
        sign=1,
        desc="Program progress",
    ),
)

SENSORS = (
    HomeConnectSensorEntityDescription(
        key=BSH_OPERATION_STATE,
        device_class=SensorDeviceClass.ENUM,
        options=[
            "Inactive",
            "Ready",
            "DelayedStart",
            "Run",
            "Pause",
            "ActionRequired",
            "Finished",
            "Error",
            "Aborting",
        ],
        desc="Operation state",
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterCoffee",
        state_class=SensorStateClass.TOTAL_INCREASING,
        desc="Coffee counter",
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterPowderCoffee",
        state_class=SensorStateClass.TOTAL_INCREASING,
        desc="Powder coffee counter",
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterHotWater",
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        desc="Hot water counter",
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterHotWaterCups",
        state_class=SensorStateClass.TOTAL_INCREASING,
        desc="Hot water cups counter",
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterHotMilk",
        state_class=SensorStateClass.TOTAL_INCREASING,
        desc="Hot milk counter",
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterFrothyMilk",
        state_class=SensorStateClass.TOTAL_INCREASING,
        desc="Frothy milk counter",
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterMilk",
        state_class=SensorStateClass.TOTAL_INCREASING,
        desc="Milk counter",
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterCoffeeAndMilk",
        state_class=SensorStateClass.TOTAL_INCREASING,
        desc="Coffee and milk counter",
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterRistrettoEspresso",
        state_class=SensorStateClass.TOTAL_INCREASING,
        desc="Ristretto espresso counter",
    ),
    HomeConnectSensorEntityDescription(
        key="BSH.Common.Status.BatteryLevel",
        device_class=SensorDeviceClass.BATTERY,
        desc="Battery level",
    ),
    HomeConnectSensorEntityDescription(
        key="BSH.Common.Status.Video.CameraState",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "Disabled",
            "Sleeping",
            "Ready",
            "StreamingLocal",
            "StreamingCloud",
            "StreamingLocalAndCloud",
            "Error",
        ],
        desc="Camera state",
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CleaningRobot.Status.LastSelectedMap",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "TempMap",
            "Map1",
            "Map2",
            "Map3",
        ],
        desc="Last selected map",
    ),
)

EVENT_SENSORS = (
    HomeConnectSensorEntityDescription(
        key=REFRIGERATION_EVENT_DOOR_ALARM_FREEZER,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="Off",
        desc="Freezer door alarm",
        appliance_types=("FridgeFreezer", "Freezer"),
    ),
    HomeConnectSensorEntityDescription(
        key=REFRIGERATION_EVENT_DOOR_ALARM_REFRIGERATOR,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="Off",
        desc="Refrigerator door alarm",
        appliance_types=("FridgeFreezer", "Refrigerator"),
    ),
    HomeConnectSensorEntityDescription(
        key=REFRIGERATION_EVENT_TEMP_ALARM_FREEZER,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="Off",
        desc="Freezer temperature alarm",
        appliance_types=("FridgeFreezer", "Freezer"),
    ),
    HomeConnectSensorEntityDescription(
        key=COFFEE_EVENT_BEAN_CONTAINER_EMPTY,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="Off",
        desc="Bean container empty",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=COFFEE_EVENT_WATER_TANK_EMPTY,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="Off",
        desc="Water tank empty",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=COFFEE_EVENT_DRIP_TRAY_FULL,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="Off",
        desc="Bean container empty",
        appliance_types=("CoffeeMaker",),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect sensor."""

    def get_entities() -> list[SensorEntity]:
        """Get a list of entities."""
        entities: list[SensorEntity] = []
        hc_api: ConfigEntryAuth = hass.data[DOMAIN][config_entry.entry_id]
        for device in hc_api.devices:
            entities.extend(
                HomeConnectSensor(
                    device,
                    description,
                )
                for description in EVENT_SENSORS
                if description.appliance_types
                and device.appliance.type in description.appliance_types
            )
            with contextlib.suppress(HomeConnectError):
                if device.appliance.get_programs_available():
                    entities.extend(
                        HomeConnectSensor(device, desc) for desc in BSH_PROGRAM_SENSORS
                    )
            entities.extend(
                HomeConnectSensor(device, description)
                for description in SENSORS
                if description.key in device.appliance.status
            )
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectSensor(HomeConnectEntity, SensorEntity):
    """Sensor class for Home Connect."""

    entity_description: HomeConnectSensorEntityDescription

    @property
    def available(self) -> bool:
        """Return true if the sensor is available."""
        return self._attr_native_value is not None

    async def async_update(self) -> None:
        """Update the sensor's status."""
        appliance_status = self.device.appliance.status
        if (
            self.bsh_key not in appliance_status
            or ATTR_VALUE not in appliance_status[self.bsh_key]
        ):
            self._attr_native_value = self.entity_description.default_value
            _LOGGER.debug("Updated, new state: %s", self._attr_native_value)
            return
        status = appliance_status[self.bsh_key]
        match self.device_class:
            case SensorDeviceClass.TIMESTAMP:
                if ATTR_VALUE not in status:
                    self._attr_native_value = None
                elif (
                    self._attr_native_value is not None
                    and self.entity_description.sign == 1
                    and isinstance(self._attr_native_value, datetime)
                    and self._attr_native_value < dt_util.utcnow()
                ):
                    # if the date is supposed to be in the future but we're
                    # already past it, set state to None.
                    self._attr_native_value = None
                elif (
                    BSH_OPERATION_STATE
                    in (appliance_status := self.device.appliance.status)
                    and ATTR_VALUE in appliance_status[BSH_OPERATION_STATE]
                    and appliance_status[BSH_OPERATION_STATE][ATTR_VALUE]
                    in [
                        BSH_OPERATION_STATE_RUN,
                        BSH_OPERATION_STATE_PAUSE,
                        BSH_OPERATION_STATE_FINISHED,
                    ]
                ):
                    seconds = self.entity_description.sign * float(status[ATTR_VALUE])
                    self._attr_native_value = dt_util.utcnow() + timedelta(
                        seconds=seconds
                    )
                else:
                    self._attr_native_value = None
            case SensorDeviceClass.ENUM:
                # Value comes back as an enum, we only really care about the
                # last part, so split it off
                # https://developer.home-connect.com/docs/status/operation_state
                self._attr_native_value = cast(str, status.get(ATTR_VALUE)).split(".")[
                    -1
                ]
            case _:
                self._attr_native_value = status.get(ATTR_VALUE)
        _LOGGER.debug("Updated, new state: %s", self._attr_native_value)

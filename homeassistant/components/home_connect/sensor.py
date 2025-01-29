"""Provides a sensor for Home Connect."""

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTime, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util, slugify

from . import HomeConnectConfigEntry
from .const import (
    APPLIANCES_WITH_PROGRAMS,
    ATTR_VALUE,
    BSH_DOOR_STATE,
    BSH_OPERATION_STATE,
    BSH_OPERATION_STATE_FINISHED,
    BSH_OPERATION_STATE_PAUSE,
    BSH_OPERATION_STATE_RUN,
    COFFEE_EVENT_BEAN_CONTAINER_EMPTY,
    COFFEE_EVENT_DRIP_TRAY_FULL,
    COFFEE_EVENT_WATER_TANK_EMPTY,
    DISHWASHER_EVENT_RINSE_AID_NEARLY_EMPTY,
    DISHWASHER_EVENT_SALT_NEARLY_EMPTY,
    REFRIGERATION_EVENT_DOOR_ALARM_FREEZER,
    REFRIGERATION_EVENT_DOOR_ALARM_REFRIGERATOR,
    REFRIGERATION_EVENT_TEMP_ALARM_FREEZER,
)
from .entity import HomeConnectEntity

_LOGGER = logging.getLogger(__name__)


EVENT_OPTIONS = ["confirmed", "off", "present"]


@dataclass(frozen=True, kw_only=True)
class HomeConnectSensorEntityDescription(SensorEntityDescription):
    """Entity Description class for sensors."""

    default_value: str | None = None
    appliance_types: tuple[str, ...] | None = None


BSH_PROGRAM_SENSORS = (
    HomeConnectSensorEntityDescription(
        key="BSH.Common.Option.RemainingProgramTime",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="program_finish_time",
        appliance_types=(
            "CoffeMaker",
            "CookProcessor",
            "Dishwasher",
            "Dryer",
            "Hood",
            "Oven",
            "Washer",
            "WasherDryer",
        ),
    ),
    HomeConnectSensorEntityDescription(
        key="BSH.Common.Option.Duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        appliance_types=("Oven",),
    ),
    HomeConnectSensorEntityDescription(
        key="BSH.Common.Option.ProgramProgress",
        native_unit_of_measurement=PERCENTAGE,
        translation_key="program_progress",
        appliance_types=APPLIANCES_WITH_PROGRAMS,
    ),
)

SENSORS = (
    HomeConnectSensorEntityDescription(
        key=BSH_OPERATION_STATE,
        device_class=SensorDeviceClass.ENUM,
        options=[
            "inactive",
            "ready",
            "delayedstart",
            "run",
            "pause",
            "actionrequired",
            "finished",
            "error",
            "aborting",
        ],
        translation_key="operation_state",
    ),
    HomeConnectSensorEntityDescription(
        key=BSH_DOOR_STATE,
        device_class=SensorDeviceClass.ENUM,
        options=[
            "closed",
            "locked",
            "open",
        ],
        translation_key="door",
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterCoffee",
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="coffee_counter",
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterPowderCoffee",
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="powder_coffee_counter",
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterHotWater",
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="hot_water_counter",
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterHotWaterCups",
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="hot_water_cups_counter",
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterHotMilk",
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="hot_milk_counter",
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterFrothyMilk",
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="frothy_milk_counter",
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterMilk",
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="milk_counter",
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterCoffeeAndMilk",
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="coffee_and_milk_counter",
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterRistrettoEspresso",
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="ristretto_espresso_counter",
    ),
    HomeConnectSensorEntityDescription(
        key="BSH.Common.Status.BatteryLevel",
        device_class=SensorDeviceClass.BATTERY,
        translation_key="battery_level",
    ),
    HomeConnectSensorEntityDescription(
        key="BSH.Common.Status.Video.CameraState",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "disabled",
            "sleeping",
            "ready",
            "streaminglocal",
            "streamingcloud",
            "streaminglocalancloud",
            "error",
        ],
        translation_key="camera_state",
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CleaningRobot.Status.LastSelectedMap",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "tempmap",
            "map1",
            "map2",
            "map3",
        ],
        translation_key="last_selected_map",
    ),
)

EVENT_SENSORS = (
    HomeConnectSensorEntityDescription(
        key=REFRIGERATION_EVENT_DOOR_ALARM_FREEZER,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="freezer_door_alarm",
        appliance_types=("FridgeFreezer", "Freezer"),
    ),
    HomeConnectSensorEntityDescription(
        key=REFRIGERATION_EVENT_DOOR_ALARM_REFRIGERATOR,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="refrigerator_door_alarm",
        appliance_types=("FridgeFreezer", "Refrigerator"),
    ),
    HomeConnectSensorEntityDescription(
        key=REFRIGERATION_EVENT_TEMP_ALARM_FREEZER,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="freezer_temperature_alarm",
        appliance_types=("FridgeFreezer", "Freezer"),
    ),
    HomeConnectSensorEntityDescription(
        key=COFFEE_EVENT_BEAN_CONTAINER_EMPTY,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="bean_container_empty",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=COFFEE_EVENT_WATER_TANK_EMPTY,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="water_tank_empty",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=COFFEE_EVENT_DRIP_TRAY_FULL,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="drip_tray_full",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=DISHWASHER_EVENT_SALT_NEARLY_EMPTY,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="salt_nearly_empty",
        appliance_types=("Dishwasher",),
    ),
    HomeConnectSensorEntityDescription(
        key=DISHWASHER_EVENT_RINSE_AID_NEARLY_EMPTY,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="rinse_aid_nearly_empty",
        appliance_types=("Dishwasher",),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect sensor."""

    def get_entities() -> list[SensorEntity]:
        """Get a list of entities."""
        entities: list[SensorEntity] = []
        for device in entry.runtime_data.devices:
            entities.extend(
                HomeConnectSensor(
                    device,
                    description,
                )
                for description in EVENT_SENSORS
                if description.appliance_types
                and device.appliance.type in description.appliance_types
            )
            entities.extend(
                HomeConnectProgramSensor(device, desc)
                for desc in BSH_PROGRAM_SENSORS
                if desc.appliance_types
                and device.appliance.type in desc.appliance_types
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
                    and isinstance(self._attr_native_value, datetime)
                    and self._attr_native_value < dt_util.utcnow()
                ):
                    # if the date is supposed to be in the future but we're
                    # already past it, set state to None.
                    self._attr_native_value = None
                else:
                    seconds = float(status[ATTR_VALUE])
                    self._attr_native_value = dt_util.utcnow() + timedelta(
                        seconds=seconds
                    )
            case SensorDeviceClass.ENUM:
                # Value comes back as an enum, we only really care about the
                # last part, so split it off
                # https://developer.home-connect.com/docs/status/operation_state
                self._attr_native_value = slugify(
                    cast(str, status.get(ATTR_VALUE)).split(".")[-1]
                )
            case _:
                self._attr_native_value = status.get(ATTR_VALUE)
        _LOGGER.debug("Updated, new state: %s", self._attr_native_value)


class HomeConnectProgramSensor(HomeConnectSensor):
    """Sensor class for Home Connect sensors that reports information related to the running program."""

    program_running: bool = False

    @property
    def available(self) -> bool:
        """Return true if the sensor is available."""
        # These sensors are only available if the program is running, paused or finished.
        # Otherwise, some sensors report erroneous values.
        return super().available and self.program_running

    async def async_update(self) -> None:
        """Update the sensor's status."""
        self.program_running = (
            BSH_OPERATION_STATE in (appliance_status := self.device.appliance.status)
            and ATTR_VALUE in appliance_status[BSH_OPERATION_STATE]
            and appliance_status[BSH_OPERATION_STATE][ATTR_VALUE]
            in [
                BSH_OPERATION_STATE_RUN,
                BSH_OPERATION_STATE_PAUSE,
                BSH_OPERATION_STATE_FINISHED,
            ]
        )
        if self.program_running:
            await super().async_update()
        else:
            # reset the value when the program is not running, paused or finished
            self._attr_native_value = None

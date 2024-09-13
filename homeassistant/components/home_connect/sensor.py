"""Provides a sensor for Home Connect."""

import contextlib
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
    ATTR_ALLOWED_VALUES,
    ATTR_CONSTRAINTS,
    ATTR_VALUE,
    BSH_OPERATION_STATE,
    BSH_OPERATION_STATE_FINISHED,
    BSH_OPERATION_STATE_PAUSE,
    BSH_OPERATION_STATE_RUN,
    DOMAIN,
)
from .entity import HomeConnectEntity, HomeConnectEntityDescription
from .utils import bsh_key_to_translation_key

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect sensor."""

    def get_entities():
        """Get a list of entities."""
        entities: list[HomeConnectSensorEntity] = []
        hc_api: ConfigEntryAuth = hass.data[DOMAIN][config_entry.entry_id]
        for device in hc_api.devices:
            entities += [
                HomeConnectSensorEntity(device, desc)
                for desc in BSH_SENSORS
                if desc.key in device.appliance.status
            ]
            for entity in entities:
                if entity.device_class == SensorDeviceClass.ENUM:
                    with contextlib.suppress(HomeConnectError):
                        entity.get_options()
            with contextlib.suppress(HomeConnectError):
                if device.appliance.get_programs_available():
                    entities += [
                        HomeConnectSensorEntity(device, desc)
                        for desc in BSH_PROGRAM_SENSORS
                    ]
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectSensorEntityDescription(
    HomeConnectEntityDescription,
    SensorEntityDescription,
    frozen_or_thawed=True,
):
    """Description of a Home Connect sensor entity."""

    sign: int = 1


class HomeConnectSensorEntity(HomeConnectEntity, SensorEntity):
    """Sensor class for Home Connect."""

    entity_description: HomeConnectSensorEntityDescription

    def get_options(self):
        """Get the options for this sensor."""
        try:
            data = self.device.appliance.get(f"/status/{self.bsh_key}")
        except HomeConnectError as err:
            _LOGGER.error("An error occurred: %s", err)
            self._attr_options = []
            return
        if (
            not data
            or not (constraints := data.get(ATTR_CONSTRAINTS))
            or not (options := constraints.get(ATTR_ALLOWED_VALUES))
        ):
            self._attr_options = []
            return
        self._attr_options = [bsh_key_to_translation_key(option) for option in options]

    @property
    def available(self) -> bool:
        """Return true if the sensor is available."""
        return self.native_value is not None

    async def async_update(self) -> None:
        """Update the sensor's status."""
        match self.device_class:
            case SensorDeviceClass.TIMESTAMP:
                if ATTR_VALUE not in self.status:
                    self._attr_native_value = None
                elif (
                    self.native_value is not None
                    and self.entity_description.sign == 1
                    and isinstance(self.native_value, datetime)
                    and self.native_value < dt_util.utcnow()
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
                    seconds = self.entity_description.sign * float(
                        self.status[ATTR_VALUE]
                    )
                    self._attr_native_value = dt_util.utcnow() + timedelta(
                        seconds=seconds
                    )
                else:
                    self._attr_native_value = None
            case SensorDeviceClass.ENUM:
                original_value = self.status.get(ATTR_VALUE)
                self._attr_native_value = (
                    bsh_key_to_translation_key(cast(str, original_value))
                    if original_value
                    else None
                )
                if not self.options:
                    await self.hass.async_add_executor_job(self.get_options)
                _LOGGER.debug("Updated, new state: %s", original_value)
                return
            case _:
                self._attr_native_value = self.status.get(ATTR_VALUE)
        _LOGGER.debug("Updated, new state: %s", self.native_value)


BSH_PROGRAM_SENSORS = (
    HomeConnectSensorEntityDescription(
        key="BSH.Common.Option.RemainingProgramTime",
        device_class=SensorDeviceClass.TIMESTAMP,
        sign=1,
    ),
    HomeConnectSensorEntityDescription(
        key="BSH.Common.Option.Duration",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        sign=1,
    ),
    HomeConnectSensorEntityDescription(
        key="BSH.Common.Option.ProgramProgress",
        native_unit_of_measurement=PERCENTAGE,
        sign=1,
    ),
)

BSH_SENSORS = (
    HomeConnectSensorEntityDescription(
        key=BSH_OPERATION_STATE,
        device_class=SensorDeviceClass.ENUM,
    ),
    HomeConnectSensorEntityDescription(
        key="BSH.Common.Status.DoorState",
        device_class=SensorDeviceClass.ENUM,
    ),
    HomeConnectSensorEntityDescription(
        key="Refrigeration.Common.Status.Door.BottleCooler",
        device_class=SensorDeviceClass.ENUM,
    ),
    HomeConnectSensorEntityDescription(
        key="Refrigeration.Common.Status.Door.ChillerCommon",
        device_class=SensorDeviceClass.ENUM,
    ),
    HomeConnectSensorEntityDescription(
        key="Refrigeration.Common.Status.Door.Chiller",
        device_class=SensorDeviceClass.ENUM,
    ),
    HomeConnectSensorEntityDescription(
        key="Refrigeration.Common.Status.Door.ChillerLeft",
        device_class=SensorDeviceClass.ENUM,
    ),
    HomeConnectSensorEntityDescription(
        key="Refrigeration.Common.Status.Door.ChillerRight",
        device_class=SensorDeviceClass.ENUM,
    ),
    HomeConnectSensorEntityDescription(
        key="Refrigeration.Common.Status.Door.FlexCompartment",
        device_class=SensorDeviceClass.ENUM,
    ),
    HomeConnectSensorEntityDescription(
        key="Refrigeration.Common.Status.Door.Freezer",
        device_class=SensorDeviceClass.ENUM,
    ),
    HomeConnectSensorEntityDescription(
        key="Refrigeration.Common.Status.Door.Refrigerator",
        device_class=SensorDeviceClass.ENUM,
    ),
    HomeConnectSensorEntityDescription(
        key="Refrigeration.Common.Status.Door.Refrigerator2",
        device_class=SensorDeviceClass.ENUM,
    ),
    HomeConnectSensorEntityDescription(
        key="Refrigeration.Common.Status.Door.Refrigerator3",
        device_class=SensorDeviceClass.ENUM,
    ),
    HomeConnectSensorEntityDescription(
        key="Refrigeration.Common.Status.Door.WineCompartment",
        device_class=SensorDeviceClass.ENUM,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterCoffee",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterPowderCoffee",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterHotWater",
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterHotWaterCups",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterHotMilk",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterFrothyMilk",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterMilk",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterCoffeeAndMilk",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Status.BeverageCounterRistrettoEspresso",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HomeConnectSensorEntityDescription(
        key="BSH.Common.Status.BatteryLevel",
        device_class=SensorDeviceClass.BATTERY,
    ),
    HomeConnectSensorEntityDescription(
        key="BSH.Common.Status.BatteryChargingState",
        device_class=SensorDeviceClass.ENUM,
    ),
    HomeConnectSensorEntityDescription(
        key="BSH.Common.Status.ChargingConnection",
        device_class=SensorDeviceClass.ENUM,
    ),
    HomeConnectSensorEntityDescription(
        key="BSH.Common.Status.Video.CameraState",
        device_class=SensorDeviceClass.ENUM,
    ),
    HomeConnectSensorEntityDescription(
        key="ConsumerProducts.CleaningRobot.Status.LastSelectedMap",
        device_class=SensorDeviceClass.ENUM,
    ),
)

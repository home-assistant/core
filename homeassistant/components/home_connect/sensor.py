"""Provides a sensor for Home Connect."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITIES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .api import ConfigEntryAuth, HomeConnectDevice
from .const import (
    ATTR_DEVICE,
    ATTR_VALUE,
    BSH_EVENT_PRESENT_STATE_OFF,
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
from .entity import HomeConnectEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class HomeConnectSensorEntityDescription(SensorEntityDescription):
    """Entity Description class for sensors."""

    device_class: SensorDeviceClass | None = SensorDeviceClass.ENUM
    options: list[str] | None = field(
        default_factory=lambda: ["confirmed", "off", "present"]
    )
    state_key: str
    appliance_types: tuple[str, ...]


SENSORS: tuple[HomeConnectSensorEntityDescription, ...] = (
    HomeConnectSensorEntityDescription(
        key="Door Alarm Freezer",
        translation_key="alarm_sensor_freezer",
        state_key=REFRIGERATION_EVENT_DOOR_ALARM_FREEZER,
        appliance_types=("FridgeFreezer", "Freezer"),
    ),
    HomeConnectSensorEntityDescription(
        key="Door Alarm Refrigerator",
        translation_key="alarm_sensor_fridge",
        state_key=REFRIGERATION_EVENT_DOOR_ALARM_REFRIGERATOR,
        appliance_types=("FridgeFreezer", "Refrigerator"),
    ),
    HomeConnectSensorEntityDescription(
        key="Temperature Alarm Freezer",
        translation_key="alarm_sensor_temp",
        state_key=REFRIGERATION_EVENT_TEMP_ALARM_FREEZER,
        appliance_types=("FridgeFreezer", "Freezer"),
    ),
    HomeConnectSensorEntityDescription(
        key="Bean Container Empty",
        translation_key="alarm_sensor_coffee_bean_container",
        state_key=COFFEE_EVENT_BEAN_CONTAINER_EMPTY,
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key="Water Tank Empty",
        translation_key="alarm_sensor_coffee_water_tank",
        state_key=COFFEE_EVENT_WATER_TANK_EMPTY,
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key="Drip Tray Full",
        translation_key="alarm_sensor_coffee_drip_tray",
        state_key=COFFEE_EVENT_DRIP_TRAY_FULL,
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
        for device_dict in hc_api.devices:
            entity_dicts = device_dict.get(CONF_ENTITIES, {}).get("sensor", [])
            entities += [HomeConnectSensor(**d) for d in entity_dicts]
            device: HomeConnectDevice = device_dict[ATTR_DEVICE]
            # Auto-discover entities
            entities.extend(
                HomeConnectAlarmSensor(
                    device,
                    entity_description=description,
                )
                for description in SENSORS
                if device.appliance.type in description.appliance_types
            )
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectSensor(HomeConnectEntity, SensorEntity):
    """Sensor class for Home Connect."""

    _key: str
    _sign: int

    def __init__(
        self,
        device: HomeConnectDevice,
        desc: str,
        key: str,
        unit: str,
        icon: str,
        device_class: SensorDeviceClass,
        sign: int = 1,
    ) -> None:
        """Initialize the entity."""
        super().__init__(device, desc)
        self._key = key
        self._sign = sign
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_device_class = device_class

    @property
    def available(self) -> bool:
        """Return true if the sensor is available."""
        return self._attr_native_value is not None

    async def async_update(self) -> None:
        """Update the sensor's status."""
        status = self.device.appliance.status
        if self._key not in status:
            self._attr_native_value = None
        elif self.device_class == SensorDeviceClass.TIMESTAMP:
            if ATTR_VALUE not in status[self._key]:
                self._attr_native_value = None
            elif (
                self._attr_native_value is not None
                and self._sign == 1
                and isinstance(self._attr_native_value, datetime)
                and self._attr_native_value < dt_util.utcnow()
            ):
                # if the date is supposed to be in the future but we're
                # already past it, set state to None.
                self._attr_native_value = None
            elif (
                BSH_OPERATION_STATE in status
                and ATTR_VALUE in status[BSH_OPERATION_STATE]
                and status[BSH_OPERATION_STATE][ATTR_VALUE]
                in [
                    BSH_OPERATION_STATE_RUN,
                    BSH_OPERATION_STATE_PAUSE,
                    BSH_OPERATION_STATE_FINISHED,
                ]
            ):
                seconds = self._sign * float(status[self._key][ATTR_VALUE])
                self._attr_native_value = dt_util.utcnow() + timedelta(seconds=seconds)
            else:
                self._attr_native_value = None
        else:
            self._attr_native_value = status[self._key].get(ATTR_VALUE)
            if self._key == BSH_OPERATION_STATE:
                # Value comes back as an enum, we only really care about the
                # last part, so split it off
                # https://developer.home-connect.com/docs/status/operation_state
                self._attr_native_value = cast(str, self._attr_native_value).split(".")[
                    -1
                ]
        _LOGGER.debug("Updated, new state: %s", self._attr_native_value)


class HomeConnectAlarmSensor(HomeConnectEntity, SensorEntity):
    """Sensor entity setup using SensorEntityDescription."""

    entity_description: HomeConnectSensorEntityDescription

    def __init__(
        self,
        device: HomeConnectDevice,
        entity_description: HomeConnectSensorEntityDescription,
    ) -> None:
        """Initialize the entity."""
        self.entity_description = entity_description
        super().__init__(device, self.entity_description.key)

    @property
    def available(self) -> bool:
        """Return true if the sensor is available."""
        return self._attr_native_value is not None

    async def async_update(self) -> None:
        """Update the sensor's status."""
        self._attr_native_value = (
            self.device.appliance.status.get(self.entity_description.state_key, {})
            .get(ATTR_VALUE, BSH_EVENT_PRESENT_STATE_OFF)
            .rsplit(".", maxsplit=1)[-1]
            .lower()
        )
        _LOGGER.debug(
            "Updated: %s, new state: %s",
            self._attr_unique_id,
            self._attr_native_value,
        )

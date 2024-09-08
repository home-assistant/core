"""Provides a sensor for Home Connect."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
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
from homeassistant.helpers.typing import StateType
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
    REFRIGERATION_STATUS_DOOR_CHILLER,
    REFRIGERATION_STATUS_DOOR_FREEZER,
    REFRIGERATION_STATUS_DOOR_REFRIGERATOR,
)
from .entity import HomeConnectEntity

_LOGGER = logging.getLogger(__name__)


def format_state_attr(state: str) -> str:
    """Format state values to attribute values."""
    return state.rsplit(".", maxsplit=1)[-1]


@dataclass(frozen=True, kw_only=True)
class HomeConnectSensorEntityDescription(SensorEntityDescription):
    """Entity Description class for binary sensors."""

    device_class: SensorDeviceClass | None = SensorDeviceClass.ENUM
    value_fn: Callable[[dict], StateType | date | datetime | Decimal]
    exists_fn: Callable[[HomeConnectDevice], bool]


SENSORS: tuple[HomeConnectSensorEntityDescription, ...] = (
    HomeConnectSensorEntityDescription(
        key="Chiller Door",
        options=["Closed", "Open"],
        translation_key="door_sensor",
        translation_placeholders={"name": "Chiller Door"},
        value_fn=lambda status: format_state_attr(state)
        if (state := status.get(REFRIGERATION_STATUS_DOOR_CHILLER, {}).get(ATTR_VALUE))
        else None,
        exists_fn=lambda device: REFRIGERATION_STATUS_DOOR_CHILLER
        in device.appliance.status,
    ),
    HomeConnectSensorEntityDescription(
        key="Freezer Door",
        options=["Closed", "Open"],
        translation_key="door_sensor",
        translation_placeholders={"name": "Freezer Door"},
        value_fn=lambda status: format_state_attr(state)
        if (state := status.get(REFRIGERATION_STATUS_DOOR_FREEZER, {}).get(ATTR_VALUE))
        else None,
        exists_fn=lambda device: REFRIGERATION_STATUS_DOOR_FREEZER
        in device.appliance.status,
    ),
    HomeConnectSensorEntityDescription(
        key="Refrigerator Door",
        options=["Closed", "Open"],
        translation_key="door_sensor",
        translation_placeholders={"name": "Refrigerator Door"},
        value_fn=lambda status: format_state_attr(state)
        if (
            state := status.get(REFRIGERATION_STATUS_DOOR_REFRIGERATOR, {}).get(
                ATTR_VALUE
            )
        )
        else None,
        exists_fn=lambda device: REFRIGERATION_STATUS_DOOR_REFRIGERATOR
        in device.appliance.status,
    ),
    HomeConnectSensorEntityDescription(
        key="Door Alarm Freezer",
        options=["Present", "Confirmed", "Off"],
        translation_key="alarm_sensor_freezer",
        translation_placeholders={
            "name": "Door Alarm Freezer",
        },
        value_fn=lambda status: format_state_attr(
            status.get(REFRIGERATION_EVENT_DOOR_ALARM_FREEZER, {}).get(
                ATTR_VALUE, BSH_EVENT_PRESENT_STATE_OFF
            )
        ),
        exists_fn=lambda device: device.appliance.type in ("FridgeFreezer", "Freezer"),
    ),
    HomeConnectSensorEntityDescription(
        key="Door Alarm Refrigerator",
        options=["Present", "Confirmed", "Off"],
        translation_key="alarm_sensor_fridge",
        translation_placeholders={
            "name": "Door Alarm Refrigerator",
        },
        value_fn=lambda status: format_state_attr(
            status.get(REFRIGERATION_EVENT_DOOR_ALARM_REFRIGERATOR, {}).get(
                ATTR_VALUE, BSH_EVENT_PRESENT_STATE_OFF
            )
        ),
        exists_fn=lambda device: device.appliance.type
        in ("FridgeFreezer", "Refrigerator"),
    ),
    HomeConnectSensorEntityDescription(
        key="Temperature Alarm Freezer",
        options=["Present", "Confirmed", "Off"],
        translation_key="alarm_sensor_temp",
        translation_placeholders={
            "name": "Temperature Alarm Freezer",
        },
        value_fn=lambda status: format_state_attr(
            status.get(REFRIGERATION_EVENT_TEMP_ALARM_FREEZER, {}).get(
                ATTR_VALUE, BSH_EVENT_PRESENT_STATE_OFF
            )
        ),
        exists_fn=lambda device: device.appliance.type in ("FridgeFreezer", "Freezer"),
    ),
    HomeConnectSensorEntityDescription(
        key="Bean Container Empty",
        options=["Present", "Confirmed", "Off"],
        translation_key="alarm_sensor_coffee_bean_container",
        translation_placeholders={
            "name": "Bean Container Empty",
        },
        value_fn=lambda status: format_state_attr(
            status.get(COFFEE_EVENT_BEAN_CONTAINER_EMPTY, {}).get(
                ATTR_VALUE, BSH_EVENT_PRESENT_STATE_OFF
            )
        ),
        exists_fn=lambda device: device.appliance.type == "CoffeeMaker",
    ),
    HomeConnectSensorEntityDescription(
        key="Water Tank Empty",
        options=["Present", "Confirmed", "Off"],
        translation_key="alarm_sensor_coffee_water_tank",
        translation_placeholders={
            "name": "Water Tank Empty",
        },
        value_fn=lambda status: format_state_attr(
            status.get(COFFEE_EVENT_WATER_TANK_EMPTY, {}).get(
                ATTR_VALUE, BSH_EVENT_PRESENT_STATE_OFF
            )
        ),
        exists_fn=lambda device: device.appliance.type == "CoffeeMaker",
    ),
    HomeConnectSensorEntityDescription(
        key="Drip Tray Full",
        options=["Present", "Confirmed", "Off"],
        translation_key="alarm_sensor_coffee_drip_tray",
        translation_placeholders={
            "name": "Drip Tray Full",
        },
        value_fn=lambda status: format_state_attr(
            status.get(COFFEE_EVENT_DRIP_TRAY_FULL, {}).get(
                ATTR_VALUE, BSH_EVENT_PRESENT_STATE_OFF
            )
        ),
        exists_fn=lambda device: device.appliance.type == "CoffeeMaker",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect sensor."""

    def get_entities():
        """Get a list of entities."""
        entities = []
        hc_api: ConfigEntryAuth = hass.data[DOMAIN][config_entry.entry_id]
        for device_dict in hc_api.devices:
            entity_dicts = device_dict.get(CONF_ENTITIES, {}).get("sensor", [])
            entities += [HomeConnectSensor(**d) for d in entity_dicts]
            device: HomeConnectDevice = device_dict[ATTR_DEVICE]
            # Auto-discover entities
            entities.extend(
                HomeConnectOptionSensor(
                    device,
                    entity_description=description,
                )
                for description in SENSORS
                if description.exists_fn(device)
            )
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectSensor(HomeConnectEntity, SensorEntity):
    """Sensor class for Home Connect."""

    def __init__(self, device, desc, key, unit, icon, device_class, sign=1):
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


class HomeConnectOptionSensor(HomeConnectEntity, SensorEntity):
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
        self._attr_native_value = self.entity_description.value_fn(
            self.device.appliance.status
        )
        _LOGGER.debug(
            "Updated: %s, new state: %s",
            self._attr_unique_id,
            self._attr_native_value,
        )

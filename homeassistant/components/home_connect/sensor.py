"""Provides a sensor for Home Connect."""
from datetime import datetime, timedelta
import logging
from typing import cast

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITIES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import ATTR_VALUE, BSH_OPERATION_STATE, DOMAIN
from .entity import HomeConnectEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect sensor."""

    def get_entities():
        """Get a list of entities."""
        entities = []
        hc_api = hass.data[DOMAIN][config_entry.entry_id]
        for device_dict in hc_api.devices:
            entity_dicts = device_dict.get(CONF_ENTITIES, {}).get("sensor", [])
            entities += [HomeConnectSensor(**d) for d in entity_dicts]
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
            else:
                seconds = self._sign * float(status[self._key][ATTR_VALUE])
                self._attr_native_value = dt_util.utcnow() + timedelta(seconds=seconds)
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

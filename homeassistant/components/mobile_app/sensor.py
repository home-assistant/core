"""Sensor platform for mobile_app."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_SENSOR_ATTRIBUTES,
    ATTR_SENSOR_DEVICE_CLASS,
    ATTR_SENSOR_ENTITY_CATEGORY,
    ATTR_SENSOR_ICON,
    ATTR_SENSOR_NAME,
    ATTR_SENSOR_STATE,
    ATTR_SENSOR_STATE_CLASS,
    ATTR_SENSOR_TYPE,
    ATTR_SENSOR_TYPE_SENSOR as ENTITY_TYPE,
    ATTR_SENSOR_UNIQUE_ID,
    ATTR_SENSOR_UOM,
    DOMAIN,
)
from .entity import MobileAppEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up mobile app sensor from a config entry."""
    entities = []

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]

    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    for entry in entries:
        if entry.domain != ENTITY_TYPE or entry.disabled_by:
            continue
        config: dict[str, Any] = {
            ATTR_SENSOR_ATTRIBUTES: {},
            ATTR_SENSOR_DEVICE_CLASS: entry.device_class or entry.original_device_class,
            ATTR_SENSOR_ICON: entry.original_icon,
            ATTR_SENSOR_NAME: entry.original_name,
            ATTR_SENSOR_STATE: None,
            ATTR_SENSOR_TYPE: entry.domain,
            ATTR_SENSOR_UNIQUE_ID: entry.unique_id,
            ATTR_SENSOR_UOM: entry.unit_of_measurement,
            ATTR_SENSOR_ENTITY_CATEGORY: entry.entity_category,
        }
        entities.append(MobileAppSensor(config, config_entry))

    async_add_entities(entities)

    @callback
    def handle_sensor_registration(data):
        if data[CONF_WEBHOOK_ID] != webhook_id:
            return

        async_add_entities([MobileAppSensor(data, config_entry)])

    async_dispatcher_connect(
        hass,
        f"{DOMAIN}_{ENTITY_TYPE}_register",
        handle_sensor_registration,
    )


class MobileAppSensor(MobileAppEntity, SensorEntity):
    """Representation of an mobile app sensor."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if (state := self._config[ATTR_SENSOR_STATE]) in (None, STATE_UNKNOWN):
            return None

        if (
            self.device_class
            in (
                SensorDeviceClass.DATE,
                SensorDeviceClass.TIMESTAMP,
            )
            and (timestamp := dt_util.parse_datetime(state)) is not None
        ):
            if self.device_class == SensorDeviceClass.DATE:
                return timestamp.date()
            return timestamp

        return state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self._config.get(ATTR_SENSOR_UOM)

    @property
    def state_class(self) -> str | None:
        """Return state class."""
        return self._config.get(ATTR_SENSOR_STATE_CLASS)

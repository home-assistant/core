"""Sensor platform for mobile_app."""
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID, STATE_UNKNOWN, UnitOfTemperature
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
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
from .webhook import _extract_sensor_unique_id


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


class MobileAppSensor(MobileAppEntity, RestoreSensor):
    """Representation of an mobile app sensor."""

    async def async_restore_last_state(self, last_state: State) -> None:
        """Restore previous state."""
        await super().async_restore_last_state(last_state)
        config = self._config
        if not (last_sensor_data := await self.async_get_last_sensor_data()):
            # Workaround to handle migration to RestoreSensor, can be removed
            # in HA Core 2023.4
            config[ATTR_SENSOR_STATE] = None
            webhook_id = self._entry.data[CONF_WEBHOOK_ID]
            if TYPE_CHECKING:
                assert self.unique_id is not None
            sensor_unique_id = _extract_sensor_unique_id(webhook_id, self.unique_id)
            if (
                self.device_class == SensorDeviceClass.TEMPERATURE
                and sensor_unique_id == "battery_temperature"
            ):
                config[ATTR_SENSOR_UOM] = UnitOfTemperature.CELSIUS
        else:
            config[ATTR_SENSOR_STATE] = last_sensor_data.native_value
            config[ATTR_SENSOR_UOM] = last_sensor_data.native_unit_of_measurement

        self._async_update_attr_from_config()

    @property
    def native_value(self) -> StateType | date | datetime:
        """Return the state of the sensor."""
        if (state := self._config[ATTR_SENSOR_STATE]) in (None, STATE_UNKNOWN):
            return None

        device_class = self.device_class

        if (
            device_class in (SensorDeviceClass.DATE, SensorDeviceClass.TIMESTAMP)
            # Only parse strings: if the sensor's state is restored, the state is a
            # native date or datetime, not str
            and isinstance(state, str)
            and (timestamp := dt_util.parse_datetime(state)) is not None
        ):
            if device_class == SensorDeviceClass.DATE:
                return timestamp.date()
            return timestamp

        return state

    @callback
    def _async_update_attr_from_config(self) -> None:
        """Update the entity from the config."""
        super()._async_update_attr_from_config()
        config = self._config
        self._attr_native_unit_of_measurement = config.get(ATTR_SENSOR_UOM)
        self._attr_state_class = config.get(ATTR_SENSOR_STATE_CLASS)

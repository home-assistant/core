"""Binary sensor platform for mobile_app."""
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID, STATE_ON
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_SENSOR_ATTRIBUTES,
    ATTR_SENSOR_DEVICE_CLASS,
    ATTR_SENSOR_ENTITY_CATEGORY,
    ATTR_SENSOR_ICON,
    ATTR_SENSOR_NAME,
    ATTR_SENSOR_STATE,
    ATTR_SENSOR_TYPE,
    ATTR_SENSOR_TYPE_BINARY_SENSOR as ENTITY_TYPE,
    ATTR_SENSOR_UNIQUE_ID,
    DOMAIN,
)
from .entity import MobileAppEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up mobile app binary sensor from a config entry."""
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
            ATTR_SENSOR_ENTITY_CATEGORY: entry.entity_category,
        }
        entities.append(MobileAppBinarySensor(config, config_entry))

    async_add_entities(entities)

    @callback
    def handle_sensor_registration(data):
        if data[CONF_WEBHOOK_ID] != webhook_id:
            return

        async_add_entities([MobileAppBinarySensor(data, config_entry)])

    async_dispatcher_connect(
        hass,
        f"{DOMAIN}_{ENTITY_TYPE}_register",
        handle_sensor_registration,
    )


class MobileAppBinarySensor(MobileAppEntity, BinarySensorEntity):
    """Representation of an mobile app binary sensor."""

    async def async_restore_last_state(self, last_state: State) -> None:
        """Restore previous state."""
        await super().async_restore_last_state(last_state)
        self._config[ATTR_SENSOR_STATE] = last_state.state == STATE_ON
        self._async_update_attr_from_config()

    @callback
    def _async_update_attr_from_config(self) -> None:
        """Update the entity from the config."""
        super()._async_update_attr_from_config()
        self._attr_is_on = self._config[ATTR_SENSOR_STATE]

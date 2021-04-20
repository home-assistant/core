"""A entity class for mobile_app."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ICON, CONF_NAME, CONF_UNIQUE_ID, CONF_WEBHOOK_ID
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    ATTR_SENSOR_ATTRIBUTES,
    ATTR_SENSOR_DEVICE_CLASS,
    ATTR_SENSOR_ICON,
    ATTR_SENSOR_STATE,
    ATTR_SENSOR_TYPE,
    ATTR_SENSOR_UNIQUE_ID,
    SIGNAL_SENSOR_UPDATE,
)
from .helpers import device_info


def unique_id(webhook_id, sensor_unique_id):
    """Return a unique sensor ID."""
    return f"{webhook_id}_{sensor_unique_id}"


class MobileAppEntity(RestoreEntity):
    """Representation of an mobile app entity."""

    def __init__(self, config: dict, device: DeviceEntry, entry: ConfigEntry):
        """Initialize the entity."""
        self._config = config
        self._device = device
        self._entry = entry
        self._registration = entry.data
        self._unique_id = config[CONF_UNIQUE_ID]
        self._entity_type = config[ATTR_SENSOR_TYPE]
        self._name = config[CONF_NAME]

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_SENSOR_UPDATE, self._handle_update
            )
        )
        state = await self.async_get_last_state()

        if state is None:
            return

        self.async_restore_last_state(state)

    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        self._config[ATTR_SENSOR_STATE] = last_state.state
        self._config[ATTR_SENSOR_ATTRIBUTES] = {
            **last_state.attributes,
            **self._config[ATTR_SENSOR_ATTRIBUTES],
        }
        if ATTR_ICON in last_state.attributes:
            self._config[ATTR_SENSOR_ICON] = last_state.attributes[ATTR_ICON]

    @property
    def should_poll(self) -> bool:
        """Declare that this entity pushes its state to HA."""
        return False

    @property
    def name(self):
        """Return the name of the mobile app sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the device class."""
        return self._config.get(ATTR_SENSOR_DEVICE_CLASS)

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        return self._config[ATTR_SENSOR_ATTRIBUTES]

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._config[ATTR_SENSOR_ICON]

    @property
    def unique_id(self):
        """Return the unique ID of this sensor."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return device_info(self._registration)

    @callback
    def _handle_update(self, data):
        """Handle async event updates."""
        incoming_id = unique_id(data[CONF_WEBHOOK_ID], data[ATTR_SENSOR_UNIQUE_ID])
        if incoming_id != self._unique_id:
            return

        self._config = {**self._config, **data}
        self.async_write_ha_state()

"""A entity class for mobile_app."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import (ATTR_DEVICE_ID, ATTR_DEVICE_NAME, ATTR_MANUFACTURER,
                    ATTR_MODEL, ATTR_OS_VERSION, ATTR_SENSOR_ATTRIBUTES,
                    ATTR_SENSOR_DEVICE_CLASS, ATTR_SENSOR_ICON,
                    ATTR_SENSOR_NAME, ATTR_SENSOR_TYPE, ATTR_SENSOR_UNIQUE_ID,
                    DOMAIN, SIGNAL_SENSOR_UPDATE)


class MobileAppEntity(Entity):
    """Representation of an mobile app entity."""

    def __init__(self, config: dict, device: DeviceEntry, entry: ConfigEntry):
        """Initialize the sensor."""
        self._config = config
        self._device = device
        self._entry = entry
        self._registration = entry.data
        self._sensor_id = "{}_{}".format(self._registration[CONF_WEBHOOK_ID],
                                         config[ATTR_SENSOR_UNIQUE_ID])
        self._entity_type = config[ATTR_SENSOR_TYPE]
        self.unsub_dispatcher = None

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.unsub_dispatcher = async_dispatcher_connect(self.hass,
                                                         SIGNAL_SENSOR_UPDATE,
                                                         self._handle_update)

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        if self.unsub_dispatcher is not None:
            self.unsub_dispatcher()

    @property
    def should_poll(self) -> bool:
        """Declare that this entity pushes its state to HA."""
        return False

    @property
    def name(self):
        """Return the name of the mobile app sensor."""
        return self._config[ATTR_SENSOR_NAME]

    @property
    def device_class(self):
        """Return the device class."""
        return self._config.get(ATTR_SENSOR_DEVICE_CLASS)

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return self._config[ATTR_SENSOR_ATTRIBUTES]

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._config[ATTR_SENSOR_ICON]

    @property
    def unique_id(self):
        """Return the unique ID of this sensor."""
        return self._sensor_id

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return {
            'identifiers': {
                (ATTR_DEVICE_ID, self._registration[ATTR_DEVICE_ID]),
                (CONF_WEBHOOK_ID, self._registration[CONF_WEBHOOK_ID])
            },
            'manufacturer': self._registration[ATTR_MANUFACTURER],
            'model': self._registration[ATTR_MODEL],
            'device_name': self._registration[ATTR_DEVICE_NAME],
            'sw_version': self._registration[ATTR_OS_VERSION],
            'config_entries': self._device.config_entries
        }

    async def async_update(self):
        """Get the latest state of the sensor."""
        data = self.hass.data[DOMAIN]
        try:
            self._config = data[self._entity_type][self._sensor_id]
        except KeyError:
            return

    @callback
    def _handle_update(self, data):
        """Handle async event updates."""
        self._config = data
        self.async_schedule_update_ha_state()

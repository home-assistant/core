"""PlaatoEntity class."""
from pyplaato.models.device import PlaatoDevice

from homeassistant.helpers import entity

from .const import DEVICE, DEVICE_ID, DEVICE_NAME, DEVICE_TYPE, DOMAIN, SENSOR_DATA


class PlaatoEntity(entity.Entity):
    """Representation of a Plaato Entity."""

    def __init__(self, data, sensor_type, coordinator=None):
        """Initialize the sensor."""
        sensor_data = data[SENSOR_DATA] if coordinator is None else coordinator.data
        self._coordinator = coordinator
        self._sensor_data: PlaatoDevice = sensor_data
        self._sensor_type = sensor_type
        self._device_id = data[DEVICE][DEVICE_ID]
        self._device_type = data[DEVICE][DEVICE_TYPE]
        self._device_name = data[DEVICE][DEVICE_NAME]
        self._name = self._sensor_data.get_sensor_name(sensor_type)
        self._attributes = PlaatoEntity._to_snake_case(self._sensor_data.attributes)
        self._state = 0

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name}".title()

    @property
    def unique_id(self):
        """Return the unique ID of this sensor."""
        return f"{self._device_id}_{self._sensor_type}"

    @property
    def device_info(self):
        """Get device info."""
        device_info = {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_name,
            "manufacturer": "Plaato",
            "model": self._device_type,
        }

        if self._sensor_data.firmware_version != "":
            device_info["sw_version"] = self._sensor_data.firmware_version

        return device_info

    @property
    def device_state_attributes(self):
        """Return the state attributes of the monitored installation."""
        if self._attributes is not None:
            return self._attributes

    @property
    def available(self):
        """Return if sensor is available."""
        if self._coordinator is not None:
            return self._coordinator.last_update_success
        return True

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        if self._coordinator is not None:
            self.async_on_remove(
                self._coordinator.async_add_listener(self.async_write_ha_state)
            )
        else:
            self.async_on_remove(
                self.hass.helpers.dispatcher.async_dispatcher_connect(
                    f"{DOMAIN}_{self.unique_id}", self.async_write_ha_state
                )
            )

    @staticmethod
    def _to_snake_case(dictionary: dict):
        return {k.lower().replace(" ", "_"): v for k, v in dictionary.items()}

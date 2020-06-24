"""PlaatoEntity class."""

from pyplaato.plaato import PlaatoDeviceType

from homeassistant.helpers import entity

from .const import DOMAIN


class PlaatoEntity(entity.Entity):
    """Representation of a Plaato Entity."""

    def __init__(self, device_id, sensor_type, device_name, coordinator=None):
        """Initialize the sensor."""
        self._coordinator = coordinator
        self._device_id = device_id
        self._sensor_type = sensor_type
        self._device_type = PlaatoDeviceType.Airlock
        self._device_name = device_name
        self._name = f"{device_name} {sensor_type}"
        self._attributes = None

        if coordinator is not None:
            self._device_type = coordinator.data.device_type
            sensor_name = coordinator.data.get_sensor_name(self._sensor_type)
            self._name = f"{device_name} {sensor_name}"
            self._attributes = PlaatoEntity._to_snake_case(coordinator.data.attributes)

        self._state = 0

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN} {self._device_type} {self._name}".title()

    @property
    def unique_id(self):
        """Return the unique ID of this sensor."""
        return f"{self._device_id}_{self._sensor_type}"

    @property
    def device_info(self):
        """Get device info."""
        fw_version = ""
        if self._coordinator is not None:
            fw_version = self._coordinator.data.firmware_version
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_name,
            "manufacturer": "Plaato",
            "model": self._device_type,
            "sw_version": fw_version,
        }

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
            self.async_on_remove(self._coordinator.async_add_listener(self.async_write_ha_state))
        else:
            self.async_on_remove(
                self.hass.helpers.dispatcher.async_dispatcher_connect(
                    f"{DOMAIN}_{self.unique_id}", self.async_write_ha_state
                )
            )

    async def async_will_remove_from_hass(self):
        """When entity will be removed from hass."""
        if self._coordinator is not None:
            self._coordinator.async_remove_listener(self.async_write_ha_state)

    @staticmethod
    def _to_snake_case(dictionary: dict):
        return {k.lower().replace(" ", "_"): v for k, v in dictionary.items()}

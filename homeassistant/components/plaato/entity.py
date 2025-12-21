"""PlaatoEntity class."""

from typing import Any

from pyplaato.models.device import PlaatoDevice

from homeassistant.helpers import entity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    DEVICE,
    DEVICE_ID,
    DEVICE_NAME,
    DEVICE_TYPE,
    DOMAIN,
    EXTRA_STATE_ATTRIBUTES,
    SENSOR_DATA,
    SENSOR_SIGNAL,
)


class PlaatoEntity(entity.Entity):
    """Representation of a Plaato Entity."""

    _attr_should_poll = False

    def __init__(self, data, sensor_type, coordinator=None):
        """Initialize the sensor."""
        self._coordinator = coordinator
        self._entry_data = data
        self._sensor_type = sensor_type
        self._device_id = data[DEVICE][DEVICE_ID]
        self._device_type = data[DEVICE][DEVICE_TYPE]
        self._device_name = data[DEVICE][DEVICE_NAME]
        self._attr_unique_id = f"{self._device_id}_{self._sensor_type}"
        self._attr_name = f"{DOMAIN} {self._device_type} {self._device_name} {self._sensor_name}".title()
        sw_version = None
        if firmware := self._sensor_data.firmware_version:
            sw_version = firmware
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer="Plaato",
            model=self._device_type,
            name=self._device_name,
            sw_version=sw_version,
        )

    @property
    def _attributes(self) -> dict:
        return PlaatoEntity._to_snake_case(self._sensor_data.attributes)

    @property
    def _sensor_name(self) -> str:
        return self._sensor_data.get_sensor_name(self._sensor_type)

    @property
    def _sensor_data(self) -> PlaatoDevice:
        if self._coordinator:
            return self._coordinator.data
        return self._entry_data[SENSOR_DATA]

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the monitored installation."""
        if self._attributes:
            return {
                attr_key: self._attributes[plaato_key]
                for attr_key, plaato_key in EXTRA_STATE_ATTRIBUTES.items()
                if plaato_key in self._attributes
                and self._attributes[plaato_key] is not None
            }
        return None

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        if self._coordinator is not None:
            return self._coordinator.last_update_success
        return True

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        if self._coordinator is not None:
            self.async_on_remove(
                self._coordinator.async_add_listener(self.async_write_ha_state)
            )
        else:
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    SENSOR_SIGNAL % (self._device_id, self._sensor_type),
                    self.async_write_ha_state,
                )
            )

    @staticmethod
    def _to_snake_case(dictionary: dict):
        return {k.lower().replace(" ", "_"): v for k, v in dictionary.items()}

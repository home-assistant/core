"""Support for Tado sensors for each zone."""
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA, DOMAIN, SIGNAL_TADO_UPDATE_RECEIVED, TYPE_BATTERY, TYPE_POWER
from .entity import TadoDeviceEntity

_LOGGER = logging.getLogger(__name__)

DEVICE_SENSORS = {
    TYPE_BATTERY: [
        "battery state",
        "connection state",
    ],
    TYPE_POWER: [
        "connection state",
    ],
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the Tado sensor platform."""

    tado = hass.data[DOMAIN][entry.entry_id][DATA]
    devices = tado.devices
    entities = []

    # Create device sensors
    for device in devices:
        if "batteryState" in device:
            device_type = TYPE_BATTERY
        else:
            device_type = TYPE_POWER

        entities.extend(
            [
                TadoDeviceSensor(tado, device, variable)
                for variable in DEVICE_SENSORS[device_type]
            ]
        )

    if entities:
        async_add_entities(entities, True)


class TadoDeviceSensor(TadoDeviceEntity, BinarySensorEntity):
    """Representation of a tado Sensor."""

    def __init__(self, tado, device_info, device_variable):
        """Initialize of the Tado Sensor."""
        self._tado = tado
        super().__init__(device_info)

        self.device_variable = device_variable

        self._unique_id = f"{device_variable} {self.device_id} {tado.home_id}"

        self._state = None

    async def async_added_to_hass(self):
        """Register for sensor updates."""

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_TADO_UPDATE_RECEIVED.format(
                    self._tado.home_id, "device", self.device_id
                ),
                self._async_update_callback,
            )
        )
        self._async_update_device_data()

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.device_name} {self.device_variable}"

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this sensor."""
        if self.device_variable == "battery state":
            return DEVICE_CLASS_BATTERY
        if self.device_variable == "connection state":
            return DEVICE_CLASS_CONNECTIVITY
        return None

    @callback
    def _async_update_callback(self):
        """Update and write state."""
        self._async_update_device_data()
        self.async_write_ha_state()

    @callback
    def _async_update_device_data(self):
        """Handle update callbacks."""
        for device in self._tado.devices:
            if device["serialNo"] == self.device_id:
                self._device_info = device
                break

        if self.device_variable == "battery state":
            self._state = self._device_info["batteryState"] == "LOW"
        elif self.device_variable == "connection state":
            self._state = self._device_info.get("connectionState", {}).get(
                "value", False
            )

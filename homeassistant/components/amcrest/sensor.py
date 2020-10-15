"""Support for Amcrest IP camera sensors."""
from datetime import timedelta
import logging

from amcrest import AmcrestError

from homeassistant.const import CONF_NAME, CONF_SENSORS, PERCENTAGE
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import (
    DATA_AMCREST,
    DEVICES,
    SENSOR_SCAN_INTERVAL_SECS,
    SERVICE_UPDATE,
    CONF_SENSOR_PTZ_PRESET,
    CONF_SENSOR_SDCARD,
)
from .helpers import log_update_error, service_signal

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=SENSOR_SCAN_INTERVAL_SECS)

SENSORS = {
    CONF_SENSOR_PTZ_PRESET: ["PTZ Preset", None, "mdi:camera-iris"],
    CONF_SENSOR_SDCARD: ["SD Used", PERCENTAGE, "mdi:sd"],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a sensor for an Amcrest IP Camera."""
    if config_entry is None:
        return

    name = config_entry.data[CONF_NAME]
    device = hass.data[DATA_AMCREST][DEVICES][name]
    async_add_entities(
        [
            AmcrestSensor(name, device, sensor_type)
            for sensor_type in config_entry.options.get(CONF_SENSORS)
        ],
        True,
    )


class AmcrestSensor(Entity):
    """A sensor implementation for Amcrest IP camera."""

    def __init__(self, name, device, sensor_type):
        """Initialize a sensor for Amcrest camera."""
        self._name = f"{name} {SENSORS[sensor_type][0]}"
        self._signal_name = name
        self._api = device.api
        self._sensor_type = sensor_type
        self._state = None
        self._attrs = {}
        self._unit_of_measurement = SENSORS[sensor_type][1]
        self._icon = SENSORS[sensor_type][2]
        self._unsub_dispatcher = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return self._unit_of_measurement

    @property
    def available(self):
        """Return True if entity is available."""
        return self._api.available

    def update(self):
        """Get the latest data and updates the state."""
        if not self.available:
            return
        _LOGGER.debug("Updating %s sensor", self._name)

        try:
            if self._sensor_type == CONF_SENSOR_PTZ_PRESET:
                self._state = self._api.ptz_presets_count

            elif self._sensor_type == CONF_SENSOR_SDCARD:
                storage = self._api.storage_all
                try:
                    self._attrs[
                        "Total"
                    ] = f"{storage['total'][0]:.2f} {storage['total'][1]}"
                except ValueError:
                    self._attrs[
                        "Total"
                    ] = f"{storage['total'][0]} {storage['total'][1]}"
                try:
                    self._attrs[
                        "Used"
                    ] = f"{storage['used'][0]:.2f} {storage['used'][1]}"
                except ValueError:
                    self._attrs["Used"] = f"{storage['used'][0]} {storage['used'][1]}"
                try:
                    self._state = f"{storage['used_percent']:.2f}"
                except ValueError:
                    self._state = storage["used_percent"]
        except AmcrestError as error:
            log_update_error(_LOGGER, "update", self.name, "sensor", error)

    async def async_on_demand_update(self):
        """Update state."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Subscribe to update signal."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass,
            service_signal(SERVICE_UPDATE, self._signal_name),
            self.async_on_demand_update,
        )

    async def async_will_remove_from_hass(self):
        """Disconnect from update signal."""
        self._unsub_dispatcher()

"""Support for Amcrest IP camera sensors."""
from __future__ import annotations

import copy
from datetime import timedelta
import logging

from amcrest import AmcrestError

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import CONF_NAME, CONF_SENSORS, PERCENTAGE
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_AMCREST, DEVICES, SENSOR_SCAN_INTERVAL_SECS, SERVICE_UPDATE
from .helpers import log_update_error, service_signal

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=SENSOR_SCAN_INTERVAL_SECS)

SENSOR_PTZ_PRESET = "ptz_preset"
SENSOR_SDCARD = "sdcard"


SENSORS: dict[str, SensorEntityDescription] = {
    SENSOR_PTZ_PRESET: SensorEntityDescription(
        key=SENSOR_PTZ_PRESET, name="PTZ Preset", icon="mdi:camera-iris"
    ),
    SENSOR_SDCARD: SensorEntityDescription(
        key=SENSOR_SDCARD, name="SD Used", unit_of_measurement=PERCENTAGE, icon="mdi:sd"
    ),
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a sensor for an Amcrest IP Camera."""
    if discovery_info is None:
        return

    name = discovery_info[CONF_NAME]
    device = hass.data[DATA_AMCREST][DEVICES][name]
    async_add_entities(
        [
            AmcrestSensor(name, device, SENSORS[sensor_type])
            for sensor_type in discovery_info[CONF_SENSORS]
        ],
        True,
    )


class AmcrestSensor(SensorEntity):
    """A sensor implementation for Amcrest IP camera."""

    def __init__(self, name, device, description):
        """Initialize a sensor for Amcrest camera."""
        # make copy do not change original dict
        self.entity_description = copy(description)
        self.entity_description.name = f"{name} {self.entity_description.name}"
        self._signal_name = name
        self._api = device.api
        self._attr_extra_state_attributes = {}
        self._unsub_dispatcher = None

    @property
    def available(self):
        """Return True if entity is available."""
        return self._api.available

    def update(self):
        """Get the latest data and updates the state."""
        if not self.available:
            return
        _LOGGER.debug("Updating %s sensor", self.entity_description.name)

        try:
            if self.entity_description.key == SENSOR_PTZ_PRESET:
                self._attr_state = self._api.ptz_presets_count

            elif self.entity_description.key == SENSOR_SDCARD:
                storage = self._api.storage_all
                try:
                    self._attr_extra_state_attributes[
                        "Total"
                    ] = f"{storage['total'][0]:.2f} {storage['total'][1]}"
                except ValueError:
                    self._attr_extra_state_attributes[
                        "Total"
                    ] = f"{storage['total'][0]} {storage['total'][1]}"
                try:
                    self._attr_extra_state_attributes[
                        "Used"
                    ] = f"{storage['used'][0]:.2f} {storage['used'][1]}"
                except ValueError:
                    self._attr_extra_state_attributes[
                        "Used"
                    ] = f"{storage['used'][0]} {storage['used'][1]}"
                try:
                    self._attr_state = f"{storage['used_percent']:.2f}"
                except ValueError:
                    self._attr_state = storage["used_percent"]
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

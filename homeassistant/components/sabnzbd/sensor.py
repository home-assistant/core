"""Support for monitoring an SABnzbd NZB client."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import (
    DATA_SABNZBD,
    SENSOR_TYPES,
    SIGNAL_SABNZBD_UPDATED,
    SabnzbdSensorEntityDescription,
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the SABnzbd sensors."""
    if discovery_info is None:
        return

    sab_api_data = hass.data[DATA_SABNZBD]
    sensors = sab_api_data.sensors
    client_name = sab_api_data.name
    async_add_entities(
        [
            SabnzbdSensor(sab_api_data, client_name, description)
            for description in SENSOR_TYPES
            if description.key in sensors
        ]
    )


class SabnzbdSensor(SensorEntity):
    """Representation of an SABnzbd sensor."""

    entity_description: SabnzbdSensorEntityDescription
    _attr_should_poll = False

    def __init__(
        self, sabnzbd_api_data, client_name, description: SabnzbdSensorEntityDescription
    ):
        """Initialize the sensor."""
        self.entity_description = description
        self._sabnzbd_api = sabnzbd_api_data
        self._attr_name = f"{client_name} {description.name}"

    async def async_added_to_hass(self):
        """Call when entity about to be added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_SABNZBD_UPDATED, self.update_state
            )
        )

    def update_state(self, args):
        """Get the latest data and updates the states."""
        self._attr_native_value = self._sabnzbd_api.get_queue_field(
            self.entity_description.field_name
        )

        if self.entity_description.key == "speed":
            self._attr_native_value = round(float(self._attr_native_value) / 1024, 1)
        elif "size" in self.entity_description.key:
            self._attr_native_value = round(float(self._attr_native_value), 2)

        self.schedule_update_ha_state()

"""Support for monitoring an SABnzbd NZB client."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, SENSOR_TYPES, SIGNAL_SABNZBD_UPDATED, SabnzbdApiData
from ...config_entries import ConfigEntry
from ...core import HomeAssistant
from ...helpers.entity_platform import AddEntitiesCallback
from .const import KEY_API, KEY_NAME


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Sabnzbd sensor entry."""

    sab_api = hass.data[DOMAIN][config_entry.entry_id][KEY_API]
    client_name = hass.data[DOMAIN][config_entry.entry_id][KEY_NAME]
    sab_api_data = SabnzbdApiData(sab_api)

    async_add_entities(
        [SabnzbdSensor(sensor, sab_api_data, client_name) for sensor in SENSOR_TYPES]
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

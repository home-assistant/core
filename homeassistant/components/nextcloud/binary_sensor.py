"""Summary binary data from Nextcoud."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import NextcloudEntity, NextcloudMonitorWrapper
from .const import BINARY_SENSORS, DATA_KEY_API, DATA_KEY_COORDINATOR, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Nextcloud sensors."""
    binary_sensors = []

    instance_name = entry.data[CONF_NAME]
    ncm_data = hass.data[DOMAIN][instance_name]

    for name in ncm_data[DATA_KEY_API].data:
        if name in BINARY_SENSORS:
            binary_sensors.append(
                NextcloudBinarySensor(
                    ncm_data[DATA_KEY_API],
                    ncm_data[DATA_KEY_COORDINATOR],
                    instance_name,
                    entry.entry_id,
                    name,
                )
            )
    async_add_entities(binary_sensors, True)


class NextcloudBinarySensor(NextcloudEntity, BinarySensorEntity):
    """Represents a Nextcloud binary sensor."""

    def __init__(
        self,
        api: NextcloudMonitorWrapper,
        coordinator: DataUpdateCoordinator,
        name: str,
        server_unique_id: str,
        item: str,
    ) -> None:
        """Initialize the Nextcloud binary sensor."""

        super().__init__(api, coordinator, name, server_unique_id)

        self._item = item
        self._is_on = None
        self._attr_unique_id = f"{DOMAIN}_{self._name}_{self._item}"

    @property
    def icon(self) -> str:
        """Return the icon for this binary sensor."""
        return "mdi:cloud"

    @property
    def name(self) -> str:
        """Return the name for this binary sensor."""
        return f"{DOMAIN}_{self._name}_{self._item}"

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.api.data[self._item] == "yes"
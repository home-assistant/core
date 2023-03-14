"""Summary data from Nextcoud."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import NextcloudEntity, NextcloudMonitorWrapper
from .const import DATA_KEY_API, DATA_KEY_COORDINATOR, DOMAIN, SENSORS


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Nextcloud sensors."""
    sensors = []

    instance_name = entry.data[CONF_NAME]
    ncm_data = hass.data[DOMAIN][instance_name]

    for name in ncm_data[DATA_KEY_API].data:
        if name in SENSORS:
            sensors.append(
                NextcloudSensor(
                    ncm_data[DATA_KEY_API],
                    ncm_data[DATA_KEY_COORDINATOR],
                    instance_name,
                    entry.entry_id,
                    name,
                )
            )
    async_add_entities(sensors, True)


class NextcloudSensor(NextcloudEntity, SensorEntity):
    """Represents a Nextcloud sensor."""

    def __init__(
        self,
        api: NextcloudMonitorWrapper,
        coordinator: DataUpdateCoordinator,
        name: str,
        server_unique_id: str,
        item: str,
    ) -> None:
        """Initialize the Nextcloud sensor."""
        super().__init__(api, coordinator, name, server_unique_id)

        self._item = item
        self._state = None
        self._attr_unique_id = f"{DOMAIN}_{self._name}_{self._item}"

    @property
    def icon(self) -> str:
        """Return the icon for this sensor."""
        return "mdi:cloud"

    @property
    def name(self) -> str:
        """Return the name for this sensor."""
        return f"{DOMAIN}_{self._name}_{self._item}"

    @property
    def native_value(self) -> str:
        """Return the state for this sensor."""
        return self.api.data[self._item]
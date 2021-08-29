"""The iotawatt integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from httpx import AsyncClient
from iotawattpy.iotawatt import Iotawatt

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    COORDINATOR,
    DEFAULT_ICON,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    IOTAWATT_API,
    SIGNAL_ADD_DEVICE,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up iotawatt from a config entry."""
    polling_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    session = AsyncClient()
    if "username" in entry.data.keys():
        api = Iotawatt(
            entry.data["name"],
            entry.data["host"],
            session,
            entry.data["username"],
            entry.data["password"],
        )
    else:
        api = Iotawatt(
            entry.data["name"],
            entry.data["host"],
            session,
        )

    coordinator = IotawattUpdater(
        hass,
        api=api,
        name="IoTaWatt",
        update_interval=polling_interval,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORDINATOR: coordinator,
        IOTAWATT_API: api,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


class IotawattUpdater(DataUpdateCoordinator):
    """Class to manage fetching update data from the IoTaWatt Energy Device."""

    def __init__(
        self, hass: HomeAssistant, api: str, name: str, update_interval: int
    ) -> None:
        """Initialize IotaWattUpdater object."""
        self.api = api
        self.sensorlist: dict[str, list[str]] = {}

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=name,
            update_interval=timedelta(seconds=update_interval),
        )

    async def _async_update_data(self):
        """Fetch sensors from IoTaWatt device."""

        await self.api.update()
        sensors = self.api.getSensors()

        for sensor in sensors["sensors"]:
            if sensor not in self.sensorlist:
                to_add = {
                    "entity": sensor,
                    "mac_address": sensors["sensors"][sensor].hub_mac_address,
                    "name": sensors["sensors"][sensor].getName(),
                }
                async_dispatcher_send(self.hass, SIGNAL_ADD_DEVICE, to_add)
                self.sensorlist[sensor] = sensors["sensors"][sensor]

        return sensors


class IotaWattEntity(CoordinatorEntity):
    """Defines the base IoTaWatt Energy Device entity."""

    def __init__(self, coordinator: IotawattUpdater, entity, mac_address, name):
        """Initialize the IoTaWatt Entity."""
        super().__init__(coordinator)

        self._entity = entity
        self._attr_name = name
        self._attr_icon = DEFAULT_ICON
        self._attr_unique_id = mac_address

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._attr_unique_id

    @property
    def name(self):
        """Return the name of the entity."""
        return self._attr_name

    @property
    def icon(self):
        """Return the icon for the entity."""
        return self._attr_icon

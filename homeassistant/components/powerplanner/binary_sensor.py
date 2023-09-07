"""Power planner plan sensor."""
from datetime import datetime, timedelta
import logging
from threading import Timer

import aiohttp
import async_timeout
from powerplanner import PowerplannerHub

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import slugify

from .const import DOMAIN
from .entity import PowerPlannerEntityBase

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PowerPlanner from a config entry."""

    er.async_get(hass)
    hub: PowerplannerHub = hass.data[DOMAIN][config_entry.entry_id]
    hub.add_sensor_callback = async_add_entities
    coordinator = UpdateCoordinator(hass, hub, config_entry)
    coordinator.set_update_interval(12)
    await coordinator.async_config_entry_first_refresh()


class PPSensorEntity(PowerPlannerEntityBase, CoordinatorEntity, BinarySensorEntity):
    """An pp sensor entity using CoordinatorEntity."""

    def __init__(self, coordinator, schedule_name, hub: PowerplannerHub) -> None:
        """Init with a reference to the schedulename."""
        PowerPlannerEntityBase.__init__(self, hash(hub.api_key))
        CoordinatorEntity.__init__(self, coordinator, context=schedule_name)

        self._attr_is_on = False
        self._attr_name = "powerplanner." + schedule_name
        self._attr_device_class = BinarySensorDeviceClass.RUNNING
        self._attr_unique_id = slugify(f"sensor_powerplanner_{schedule_name}")
        self.schedule_name = schedule_name
        self.hub = hub
        self.coordinator = coordinator
        self.t: Timer

    @property
    def is_on(self) -> bool | None:
        """The state parsed from the cached schedule."""
        return self.hub.is_on(self.schedule_name)

    @property
    def next_change(self) -> datetime | None:
        """Returns the datetime when the next change occurs."""
        return self.hub.get_next_change(self.schedule_name)

    def schedule_update(self) -> None:
        """Notify HA that the state has changed and start a new timer."""
        if hasattr(self, "t") and self.t.is_alive():
            self.t.cancel()

        self.async_write_ha_state()
        time_to_change = self.hub.time_to_change(self.schedule_name)

        if time_to_change == 0:
            return

        self.t = Timer(time_to_change, self.schedule_update)
        self.t.start()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
        self.schedule_update()


class UpdateCoordinator(DataUpdateCoordinator):
    """Update powerplanner data coordinator."""

    def __init__(
        self, hass: HomeAssistant, hub: PowerplannerHub, entry: ConfigEntry
    ) -> None:
        """Start a timed updater from powerplanner service."""
        super().__init__(hass, _LOGGER, name="powerplanner sensor")
        self.config_entry = entry
        self.hub = hub

    def set_update_interval(self, seconds: int):
        """Set the update timer in seconds."""
        self.update_interval = timedelta(seconds=seconds)

    async def _async_update_data(self):
        async with async_timeout.timeout(30):
            _LOGGER.debug("Updating powerplanner schedules")
            try:
                await self.hub.update()
                if self.hub.plans_changed:
                    await self._sync_sensors()

                return self.hub.schedules

            except aiohttp.ClientConnectorError as error:
                _LOGGER.error("Error updating powerplanner: %s", error)

    async def _sync_sensors(self):
        for plan in self.hub.new_plans:
            _LOGGER.debug("Adding new plan %s", plan)
            sensor = PPSensorEntity(self, plan, self.hub)
            self.hub.add_sensor(sensor)

        for plan in self.hub.old_plans:
            _LOGGER.debug("Removing missing plan %s", plan)
            await self.hub.remove_sensor(plan)

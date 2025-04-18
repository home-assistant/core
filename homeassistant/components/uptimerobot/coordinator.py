"""DataUpdateCoordinator for the uptimerobot integration."""

from __future__ import annotations

from pyuptimerobot import (
    UptimeRobot,
    UptimeRobotAuthenticationException,
    UptimeRobotException,
    UptimeRobotMonitor,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_ATTR_OK, COORDINATOR_UPDATE_INTERVAL, DOMAIN, LOGGER


class UptimeRobotDataUpdateCoordinator(DataUpdateCoordinator[list[UptimeRobotMonitor]]):
    """Data update coordinator for UptimeRobot."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: UptimeRobot,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=COORDINATOR_UPDATE_INTERVAL,
        )
        self._device_registry = dr.async_get(hass)
        self.api = api

    async def _async_update_data(self) -> list[UptimeRobotMonitor]:
        """Update data."""
        try:
            response = await self.api.async_get_monitors()
        except UptimeRobotAuthenticationException as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except UptimeRobotException as exception:
            raise UpdateFailed(exception) from exception

        if response.status != API_ATTR_OK:
            raise UpdateFailed(response.error.message)

        monitors: list[UptimeRobotMonitor] = response.data

        current_monitors = {
            list(device.identifiers)[0][1]
            for device in dr.async_entries_for_config_entry(
                self._device_registry, self.config_entry.entry_id
            )
        }
        new_monitors = {str(monitor.id) for monitor in monitors}
        if stale_monitors := current_monitors - new_monitors:
            for monitor_id in stale_monitors:
                if device := self._device_registry.async_get_device(
                    identifiers={(DOMAIN, monitor_id)}
                ):
                    self._device_registry.async_remove_device(device.id)

        # If there are new monitors, we should reload the config entry so we can
        # create new devices and entities.
        if self.data and new_monitors - {str(monitor.id) for monitor in self.data}:
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.config_entry.entry_id)
            )

        return monitors

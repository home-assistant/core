"""The UptimeRobot integration."""
from __future__ import annotations

from pyuptimerobot import (
    UptimeRobot,
    UptimeRobotAuthenticationException,
    UptimeRobotException,
    UptimeRobotMonitor,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_ATTR_OK, COORDINATOR_UPDATE_INTERVAL, DOMAIN, LOGGER, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up UptimeRobot from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    key: str = entry.data[CONF_API_KEY]
    if key.startswith("ur") or key.startswith("m"):
        raise ConfigEntryAuthFailed(
            "Wrong API key type detected, use the 'main' API key"
        )
    uptime_robot_api = UptimeRobot(key, async_get_clientsession(hass))
    dev_reg = dr.async_get(hass)

    hass.data[DOMAIN][entry.entry_id] = coordinator = UptimeRobotDataUpdateCoordinator(
        hass,
        config_entry_id=entry.entry_id,
        dev_reg=dev_reg,
        api=uptime_robot_api,
    )

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class UptimeRobotDataUpdateCoordinator(DataUpdateCoordinator[list[UptimeRobotMonitor]]):
    """Data update coordinator for UptimeRobot."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_id: str,
        dev_reg: dr.DeviceRegistry,
        api: UptimeRobot,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=COORDINATOR_UPDATE_INTERVAL,
        )
        self._config_entry_id = config_entry_id
        self._device_registry = dev_reg
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
                self._device_registry, self._config_entry_id
            )
        }
        new_monitors = {str(monitor.id) for monitor in monitors}
        if stale_monitors := current_monitors - new_monitors:
            for monitor_id in stale_monitors:
                if device := self._device_registry.async_get_device(
                    {(DOMAIN, monitor_id)}
                ):
                    self._device_registry.async_remove_device(device.id)

        # If there are new monitors, we should reload the config entry so we can
        # create new devices and entities.
        if self.data and new_monitors - {str(monitor.id) for monitor in self.data}:
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self._config_entry_id)
            )

        return monitors

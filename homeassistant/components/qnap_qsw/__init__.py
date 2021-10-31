"""The QNAP QSW component."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
from qnap_qsw.homeassistant import QSHA, LoginError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ASYNC_TIMEOUT, DOMAIN, SERVICE_REBOOT

PLATFORMS = ["binary_sensor", "sensor"]

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up QNAP QSW from a config entry."""
    qsha = QSHA(
        host=entry.data[CONF_HOST],
        user=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    coordinator = QnapQswDataUpdateCoordinator(hass, qsha)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async def async_reboot(call):
        """Handle reboot service call."""
        await hass.async_add_executor_job(qsha.reboot)

    hass.services.async_register(DOMAIN, SERVICE_REBOOT, async_reboot)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        hass.services.async_remove(DOMAIN, SERVICE_REBOOT)

    return unload_ok


class QnapQswDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching QNAP QSW data from the switch."""

    def __init__(self, hass: HomeAssistant, qsha: QSHA) -> None:
        """Initialize."""
        self.qsha = qsha

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    def qsha_update(self):
        """Gather QSHA update tasks."""
        tasks = [
            self.hass.async_add_executor_job(self.qsha.update_firmware_condition),
            self.hass.async_add_executor_job(self.qsha.update_firmware_info),
            self.hass.async_add_executor_job(self.qsha.update_system_board),
            self.hass.async_add_executor_job(self.qsha.update_system_sensor),
            self.hass.async_add_executor_job(self.qsha.update_system_time),
            self.hass.async_add_executor_job(self.qsha.update_firmware_update_check),
        ]

        return tasks

    async def _async_update_data(self):
        """Update data via library."""
        with async_timeout.timeout(ASYNC_TIMEOUT):
            try:
                if await self.hass.async_add_executor_job(self.qsha.login):
                    tasks = self.qsha_update()
                    for task in tasks:
                        await task
            except (ConnectionError, LoginError) as error:
                raise UpdateFailed(error) from error

        return self.qsha.data()

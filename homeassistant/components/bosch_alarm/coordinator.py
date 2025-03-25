"""Coordinator for Bosch Alarm Panel."""

from __future__ import annotations

import asyncio
import logging
import ssl

from bosch_alarm_mode2 import Panel

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_INSTALLER_CODE, CONF_USER_CODE

_LOGGER = logging.getLogger(__name__)

type BoschAlarmConfigEntry = ConfigEntry[BoschAlarmCoordinator]


class BoschAlarmCoordinator(DataUpdateCoordinator[None]):
    """Bosch alarm coordinator."""

    config_entry: BoschAlarmConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: BoschAlarmConfigEntry
    ) -> None:
        """Initialize bosch alarm coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Bosch {config_entry.data[CONF_MODEL]}",
            config_entry=config_entry,
        )
        self.panel = Panel(
            host=config_entry.data[CONF_HOST],
            port=config_entry.data[CONF_PORT],
            automation_code=config_entry.data.get(CONF_PASSWORD),
            installer_or_user_code=config_entry.data.get(
                CONF_INSTALLER_CODE, config_entry.data.get(CONF_USER_CODE)
            ),
        )

        self.panel.connection_status_observer.attach(self._on_connection_status_change)

    def _on_connection_status_change(self) -> None:
        self.last_update_success = self.panel.connection_status()
        self.async_update_listeners()

    async def _async_setup(self) -> None:
        try:
            await self.panel.connect()
        except (PermissionError, ValueError) as err:
            await self.panel.disconnect()
            raise ConfigEntryNotReady from err
        except (
            OSError,
            ConnectionRefusedError,
            ssl.SSLError,
            asyncio.exceptions.TimeoutError,
        ) as err:
            await self.panel.disconnect()
            raise ConfigEntryNotReady("Connection failed") from err

    async def _async_update_data(self) -> None:
        pass

    async def async_shutdown(self) -> None:
        """Run shutdown clean up."""
        await super().async_shutdown()
        self.panel.connection_status_observer.detach(self._on_connection_status_change)
        await self.panel.disconnect()

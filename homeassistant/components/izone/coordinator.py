"""DataUpdateCoordinator for a single iZone controller."""

from datetime import timedelta
import logging
from typing import override

import pizone

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Match legacy pizone Controller._poll_loop cadence.
UPDATE_INTERVAL = timedelta(seconds=25)

type IZoneConfigEntry = ConfigEntry[IZoneCoordinator]


class IZoneCoordinator(DataUpdateCoordinator[pizone.Controller]):
    """Refresh one controller via ``refresh_all`` only.

    DHCP / moved-host recovery stays in pizone (HTTP-fail scan nudge). After
    local commands, entities should call ``async_set_updated_data`` rather than
    requesting a full refresh.
    """

    config_entry: IZoneConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: IZoneConfigEntry,
        controller: pizone.Controller,
    ) -> None:
        """Initialize the coordinator for *controller*."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {controller.device_uid}",
            update_interval=UPDATE_INTERVAL,
        )
        self.controller = controller
        self._reload_scheduled = False

    @override
    async def _async_update_data(self) -> pizone.Controller:
        """Pull system/zone/(power) state; do not rediscover or rebind here."""
        try:
            await self.controller.refresh_all()
        except ConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except pizone.ControllerCommandError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="refresh_rejected",
                translation_placeholders={"error": str(err)},
            ) from err
        except pizone.DeviceReconfigurationError as err:
            self.async_schedule_reconfigure_reload()
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="system_reconfigured",
            ) from err
        if not self.controller.connected:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="controller_offline",
            )
        return self.controller

    @callback
    def async_schedule_reconfigure_reload(self) -> None:
        """Reload once to rebuild the zones of a reprogrammed system."""
        # A failed first refresh is retried by setup with a fresh controller.
        if (
            self._reload_scheduled
            or self.config_entry.state is not ConfigEntryState.LOADED
        ):
            return
        self._reload_scheduled = True
        self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)

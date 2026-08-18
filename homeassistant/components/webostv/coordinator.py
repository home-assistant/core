"""Coordinator for the LG webOS TV integration."""

from datetime import timedelta
from typing import override

from aiowebostv import WebOsClient, WebOsTvPairError, WebOsTvState

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_CLIENT_SECRET, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.trigger import PluggableAction
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, WEBOSTV_EXCEPTIONS

SCAN_INTERVAL = timedelta(seconds=10)

type WebOsTvConfigEntry = ConfigEntry[WebOsTvDataUpdateCoordinator]


class WebOsTvDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Coordinator for the LG webOS TV integration."""

    config_entry: WebOsTvConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: WebOsTvConfigEntry,
        client: WebOsClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=config_entry.title,
            update_interval=SCAN_INTERVAL,
        )

        self.client = client
        self.turn_on = PluggableAction(self.async_update_listeners)

    @override
    async def _async_update_data(self) -> None:
        """Connect to LG webOS TV if not connected."""
        if self.client.is_connected():
            return

        try:
            await self.client.connect()
        except WEBOSTV_EXCEPTIONS as error:
            if not self.turn_on and self.config_entry.state is ConfigEntryState.LOADED:
                # can't recover if the TV is disconnected and no turn_on action
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="device_unavailable",
                    translation_placeholders={"device": self.name},
                ) from error
        except WebOsTvPairError as error:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
                translation_placeholders={"device": self.name},
            ) from error
        else:
            update_client_key(self.hass, self.config_entry, self.client)

    async def async_handle_update(self, tv_state: WebOsTvState) -> None:
        """Handle state update from TV."""
        if self.last_update_success:
            # client.connect() trigger an update on failure,
            # avoid marking the device as available
            self.async_set_updated_data(None)


def update_client_key(
    hass: HomeAssistant, entry: WebOsTvConfigEntry, client: WebOsClient
) -> None:
    """Check and update stored client key if key has changed."""
    if client.client_key != entry.data[CONF_CLIENT_SECRET]:
        host = entry.data[CONF_HOST]
        LOGGER.debug("Updating client key for host %s", host)
        data = {CONF_HOST: host, CONF_CLIENT_SECRET: client.client_key}
        hass.config_entries.async_update_entry(entry, data=data)

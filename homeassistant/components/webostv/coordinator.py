"""Coordinator for the LG webOS TV integration."""

from datetime import timedelta
from typing import override

from aiowebostv import WebOsClient, WebOsTvPairError, WebOsTvState

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_CLIENT_SECRET, CONF_HOST
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.trigger import PluggableAction
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

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
        self.turn_on = PluggableAction(self._async_turn_on_changed)
        self.device_available = True

    @override
    async def _async_update_data(self) -> None:
        """Connect to LG webOS TV if not connected."""
        if self.client.is_connected():
            self._set_device_available(True)
            return

        try:
            await self.client.connect()
        except WEBOSTV_EXCEPTIONS:
            # can't recover if the TV is disconnected and no turn_on action,
            # automation triggers are attached only when Home Assistant is running
            self._set_device_available(
                bool(self.turn_on)
                or self.config_entry.state is not ConfigEntryState.LOADED
                or self.hass.state is not CoreState.running
            )
        except WebOsTvPairError as error:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
                translation_placeholders={"device": self.name},
            ) from error
        else:
            update_client_key(self.hass, self.config_entry, self.client)
            self._set_device_available(True)

    @callback
    def _async_turn_on_changed(self) -> None:
        """Handle turn_on action attached or removed."""
        if self.turn_on:
            self._set_device_available(True)
        self.async_update_listeners()

    def _set_device_available(self, available: bool) -> None:
        """Set device availability and log transitions."""
        if available == self.device_available:
            return
        self.device_available = available
        if available:
            LOGGER.info("Device %s is available", self.name)
        else:
            # TV turned off is expected, avoid UpdateFailed which logs an error
            LOGGER.info("Device %s is unavailable", self.name)

    async def async_handle_update(self, tv_state: WebOsTvState) -> None:
        """Handle state update from TV."""
        self.async_update_listeners()


def update_client_key(
    hass: HomeAssistant, entry: WebOsTvConfigEntry, client: WebOsClient
) -> None:
    """Check and update stored client key if key has changed."""
    if client.client_key != entry.data[CONF_CLIENT_SECRET]:
        host = entry.data[CONF_HOST]
        LOGGER.debug("Updating client key for host %s", host)
        data = {CONF_HOST: host, CONF_CLIENT_SECRET: client.client_key}
        hass.config_entries.async_update_entry(entry, data=data)

"""Coordinator for the LG webOS TV integration."""

from datetime import timedelta
from typing import cast, override

from aiowebostv import WebOsClient, WebOsTvPairError, WebOsTvState

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_CLIENT_SECRET, CONF_HOST
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import PluggableAction
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailedUnreachable,
)

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

    @override
    async def _async_update_data(self) -> None:
        """Connect to LG webOS TV if not connected."""
        if self.client.is_connected():
            return

        try:
            await self.client.connect()
        except WEBOSTV_EXCEPTIONS as error:
            # can't recover if the TV is disconnected and no turn_on action,
            # automation triggers are attached only when Home Assistant is running
            if (
                not self.turn_on
                and self.config_entry.state is ConfigEntryState.LOADED
                and self.hass.state is CoreState.running
            ):
                raise UpdateFailedUnreachable(
                    translation_domain=DOMAIN,
                    translation_key="device_unreachable",
                ) from error
        except WebOsTvPairError as error:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
                translation_placeholders={"device": self.name},
            ) from error
        else:
            update_client_key(self.hass, self.config_entry, self.client)
            dr.async_get(self.hass).async_get_or_create_from_info(
                config_entry_id=self.config_entry.entry_id,
                device_info=self.device_info,
            )

    @property
    def device_info(self) -> dr.DeviceInfo:
        """Return the device info from the TV info received on connect."""
        tv_info = self.client.tv_info
        device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, cast(str, self.config_entry.unique_id))},
            manufacturer="LG",
            name=self.config_entry.title,
        )

        maj_v = tv_info.software.get("major_ver")
        min_v = tv_info.software.get("minor_ver")
        if maj_v and min_v:
            device_info.sw_version = f"{maj_v}.{min_v}"

        if model := tv_info.system.get("modelName"):
            device_info.model = model

        if serial_number := tv_info.system.get("serialNumber"):
            device_info.serial_number = serial_number

        if connections := {
            (dr.CONNECTION_NETWORK_MAC, dr.format_mac(mac))
            for key in ("wiredInfo", "wifiInfo")
            if (mac := tv_info.connection.get(key, {}).get("macAddress"))
        }:
            device_info.connections = connections

        return device_info

    @callback
    def _async_turn_on_changed(self) -> None:
        """Handle turn_on action attached or removed."""
        if self.turn_on and not self.last_update_success:
            # recover availability without waiting for the next poll
            self.config_entry.async_create_background_task(
                self.hass, self.async_request_refresh(), "webostv turn_on refresh"
            )
        self.async_update_listeners()

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

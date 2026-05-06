"""Data update coordinator for the CatGenie integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from catgenie import CatGenieAuth, CatGenieClient, Credentials, Device
from catgenie.exceptions import CatGenieAPIError, CatGenieAuthenticationError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

SCAN_INTERVAL = timedelta(seconds=60)


@dataclass
class CatGenieRuntimeData:
    """Runtime data for CatGenie."""

    auth: CatGenieAuth
    client: CatGenieClient
    coordinator: CatGenieCoordinator


type CatGenieConfigEntry = ConfigEntry[CatGenieRuntimeData]


class CatGenieCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """Coordinator that fetches all CatGenie devices in a single API call."""

    config_entry: CatGenieConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: CatGenieConfigEntry,
        client: CatGenieClient,
        auth: CatGenieAuth,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.auth = auth

    def _update_entry_tokens(self, credentials: Credentials) -> None:
        """Persist refreshed refresh token back to the config entry."""
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={
                **self.config_entry.data,
                CONF_TOKEN: credentials.refresh_token,
            },
        )

    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch all devices from the CatGenie API."""
        try:
            # Refresh the access token if needed and retry the request once
            try:
                devices = await self.client.get_devices()
            except CatGenieAuthenticationError:
                credentials = await self.auth.refresh()
                self._update_entry_tokens(credentials)
                devices = await self.client.get_devices()
        except CatGenieAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except CatGenieAPIError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err

        return {device.manufacturer_id: device for device in devices}

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
    device_coordinators: dict[str, CatGenieDeviceCoordinator]


type CatGenieConfigEntry = ConfigEntry[CatGenieRuntimeData]


class CatGenieDeviceCoordinator(DataUpdateCoordinator[Device]):
    """Coordinator for a single CatGenie device."""

    config_entry: CatGenieConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: CatGenieConfigEntry,
        client: CatGenieClient,
        auth: CatGenieAuth,
        device: Device,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{device.manufacturer_id}",
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.auth = auth
        self.device_id = device.manufacturer_id

    def _update_entry_tokens(self, credentials: Credentials) -> None:
        """Persist refreshed refresh token back to the config entry."""
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={CONF_TOKEN: credentials.refresh_token},
        )

    async def _async_update_data(self) -> Device:
        """Fetch data for this device from the CatGenie API."""
        try:
            devices = await self.client.get_devices()
        except CatGenieAuthenticationError:
            try:
                credentials = await self.auth.refresh()
                self._update_entry_tokens(credentials)
                devices = await self.client.get_devices()
            except CatGenieAuthenticationError as refresh_err:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="authentication_failed",
                ) from refresh_err
        except CatGenieAPIError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err

        for device in devices:
            if device.manufacturer_id == self.device_id:
                return device

        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="communication_error",
            translation_placeholders={"error": f"Device {self.device_id} not found"},
        )

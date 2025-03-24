"""Coordinator for FYTA integration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging

from fyta_cli.fyta_connector import FytaConnector
from fyta_cli.fyta_exceptions import (
    FytaAuthentificationError,
    FytaConnectionError,
    FytaPasswordError,
    FytaPlantError,
)
from fyta_cli.fyta_models import Plant

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_EXPIRATION, DOMAIN

_LOGGER = logging.getLogger(__name__)

type FytaConfigEntry = ConfigEntry[FytaCoordinator]


class FytaCoordinator(DataUpdateCoordinator[dict[int, Plant]]):
    """Fyta custom coordinator."""

    config_entry: FytaConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: FytaConfigEntry, fyta: FytaConnector
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="FYTA Coordinator",
            update_interval=timedelta(minutes=4),
        )
        self.fyta = fyta
        self._plants_last_update: set[int] = set()
        self.new_device_callbacks: list[Callable[[int], None]] = []

    async def _async_update_data(
        self,
    ) -> dict[int, Plant]:
        """Fetch data from API endpoint."""

        if (
            self.fyta.expiration is None
            or self.fyta.expiration.timestamp() < datetime.now().timestamp()
        ):
            await self.renew_authentication()

        try:
            data = await self.fyta.update_all_plants()
        except (FytaConnectionError, FytaPlantError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="update_error"
            ) from err
        _LOGGER.debug("Data successfully updated")

        # data must be assigned before _async_add_remove_devices, as it is uses to set-up possible new devices
        self.data = data
        self._async_add_remove_devices()

        return data

    def _async_add_remove_devices(self) -> None:
        """Add new devices, remove non-existing devices."""
        if not self._plants_last_update:
            self._plants_last_update = set(self.fyta.plant_list.keys())

        if (
            current_plants := set(self.fyta.plant_list.keys())
        ) == self._plants_last_update:
            return

        _LOGGER.debug(
            "Check for new and removed plant(s): old plants: %s; new plants: %s",
            ", ".join(map(str, self._plants_last_update)),
            ", ".join(map(str, current_plants)),
        )

        # remove old plants
        if removed_plants := self._plants_last_update - current_plants:
            _LOGGER.debug("Removed plant(s): %s", ", ".join(map(str, removed_plants)))

            device_registry = dr.async_get(self.hass)
            for plant_id in removed_plants:
                if device := device_registry.async_get_device(
                    identifiers={
                        (
                            DOMAIN,
                            f"{self.config_entry.entry_id}-{plant_id}",
                        )
                    }
                ):
                    device_registry.async_update_device(
                        device_id=device.id,
                        remove_config_entry_id=self.config_entry.entry_id,
                    )
                    _LOGGER.debug("Device removed from device registry: %s", device.id)

        # add new devices
        if new_plants := current_plants - self._plants_last_update:
            _LOGGER.debug("New plant(s) found: %s", ", ".join(map(str, new_plants)))
            for plant_id in new_plants:
                for callback in self.new_device_callbacks:
                    callback(plant_id)
                    _LOGGER.debug("Device added: %s", plant_id)

        self._plants_last_update = current_plants

    async def renew_authentication(self) -> bool:
        """Renew access token for FYTA API."""

        try:
            credentials = await self.fyta.login()
        except FytaConnectionError as ex:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN, translation_key="config_entry_not_ready"
            ) from ex
        except (FytaAuthentificationError, FytaPasswordError) as ex:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from ex

        new_config_entry = {**self.config_entry.data}
        new_config_entry[CONF_ACCESS_TOKEN] = credentials.access_token
        new_config_entry[CONF_EXPIRATION] = credentials.expiration.isoformat()

        self.hass.config_entries.async_update_entry(
            self.config_entry, data=new_config_entry
        )

        _LOGGER.debug("Credentials successfully updated")

        return True

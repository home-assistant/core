"""Nintendo parental controls data coordinator."""

from datetime import timedelta
from functools import partial
import logging
from typing import override

from pynintendoauth.exceptions import (
    HttpException,
    InvalidOAuthConfigurationException,
    InvalidSessionTokenException,
)
from pynintendoparental import Authenticator, NintendoParental
from pynintendoparental.exceptions import NoDevicesFoundException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

type NintendoParentalControlsConfigEntry = ConfigEntry[NintendoUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = timedelta(seconds=60)


class NintendoUpdateCoordinator(DataUpdateCoordinator[None]):
    """Nintendo data update coordinator."""

    config_entry: NintendoParentalControlsConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        authenticator: Authenticator,
        config_entry: NintendoParentalControlsConfigEntry,
    ) -> None:
        """Initialize update coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=config_entry,
        )
        self.api = NintendoParental(
            authenticator, hass.config.time_zone, hass.config.language
        )
        self._watched_devices: set[str] = set()
        self._updated_devices: set[str] = set()
        self._unavailable_devices: set[str] = set()

    def device_available(self, device_id: str) -> bool:
        """Return if the device was updated in the last poll."""
        return device_id not in self._unavailable_devices

    def _device_updated(self, device_id: str) -> None:
        """Mark a device as updated in this poll."""
        self._updated_devices.add(device_id)

    @override
    async def _async_update_data(self) -> None:
        """Update data from Nintendo's API."""
        self._updated_devices.clear()
        try:
            await self.api.update()
        except InvalidOAuthConfigurationException as err:
            # pylint: disable-next=home-assistant-exception-translation-key-missing
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except NoDevicesFoundException as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="no_devices_found",
            ) from err
        except InvalidSessionTokenException as err:
            _LOGGER.debug("Session token invalid, will renew on next update")
            raise UpdateFailed from err
        except HttpException as err:
            if err.error_code == "update_required":
                raise ConfigEntryError(
                    translation_domain=DOMAIN,
                    translation_key="update_required",
                ) from err
            raise UpdateFailed(retry_after=900) from err
        # The library logs and swallows errors raised while updating a device,
        # and only runs the device callbacks after a successful update.
        unavailable = self._watched_devices - self._updated_devices
        for device_id in unavailable - self._unavailable_devices:
            _LOGGER.warning(
                "Updating Nintendo device %s failed, marking it unavailable", device_id
            )
        for device_id in self._unavailable_devices - unavailable:
            _LOGGER.info("Nintendo device %s is available again", device_id)
        self._unavailable_devices = unavailable
        for device in self.api.devices.values():
            if device.device_id not in self._watched_devices:
                self._watched_devices.add(device.device_id)
                device.add_device_callback(
                    partial(self._device_updated, device.device_id)
                )

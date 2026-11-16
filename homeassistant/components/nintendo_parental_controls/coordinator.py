"""Nintendo parental controls data coordinator."""

from datetime import timedelta
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
        self._unavailable_devices: set[str] = set()

    def device_available(self, device_id: str) -> bool:
        """Return if the device was updated in the last poll."""
        return device_id not in self._unavailable_devices

    @override
    async def _async_update_data(self) -> None:
        """Update data from Nintendo's API."""
        try:
            await self.api.discover_devices()
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
        unavailable: set[str] = set()
        for device in self.api.devices.values():
            was_unavailable = device.device_id in self._unavailable_devices
            try:
                await device.update()
            except HttpException as err:
                unavailable.add(device.device_id)
                if not was_unavailable:
                    _LOGGER.warning(
                        "Updating Nintendo device %s failed, marking it unavailable: %s",
                        device.name,
                        err,
                    )
            else:
                if was_unavailable:
                    _LOGGER.info("Nintendo device %s is available again", device.name)
        self._unavailable_devices = unavailable

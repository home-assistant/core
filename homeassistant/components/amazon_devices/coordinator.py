"""Support for Amazon Devices."""

from datetime import timedelta

from aioamazondevices import AmazonDevice, AmazonEchoApi, CannotConnect
from aioamazondevices.exceptions import CannotAuthenticate, CannotRetrieveData

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import _LOGGER, CONF_LOGIN_DATA, DOMAIN

type AmazonConfigEntry = ConfigEntry[AmazonDevicesCoordinator]


class AmazonDevicesCoordinator(DataUpdateCoordinator[dict[str, AmazonDevice]]):
    """Base coordinator for Amazon Devices."""

    config_entry: AmazonConfigEntry
    api: AmazonEchoApi

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AmazonConfigEntry,
    ) -> None:
        """Initialize the scanner."""
        username = entry.data[CONF_USERNAME]
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {username}",
            config_entry=entry,
            update_interval=timedelta(seconds=30),
        )
        self.api = AmazonEchoApi(
            entry.data[CONF_COUNTRY],
            username,
            entry.data[CONF_PASSWORD],
            entry.data[CONF_LOGIN_DATA],
        )

    async def _async_update_data(self) -> dict[str, AmazonDevice]:
        """Update device data."""
        try:
            await self.api.login_mode_stored_data()
            return await self.api.get_devices_data()
        except (CannotConnect, CannotRetrieveData) as err:
            raise UpdateFailed(repr(err)) from err
        except CannotAuthenticate as err:
            raise ConfigEntryError("Could not authenticate") from err

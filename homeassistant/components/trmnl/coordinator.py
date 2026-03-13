"""Define an object to manage fetching TRMNL data."""

from __future__ import annotations

from datetime import timedelta

from trmnl import TRMNLClient
from trmnl.exceptions import TRMNLAuthenticationError, TRMNLError
from trmnl.models import Device

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type TRMNLConfigEntry = ConfigEntry[TRMNLCoordinator]


class TRMNLCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """Class to manage fetching TRMNL data."""

    config_entry: TRMNLConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TRMNLConfigEntry,
        client: TRMNLClient,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(hours=1),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch data from TRMNL."""
        try:
            devices = await self.client.get_devices()
        except TRMNLAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from err
        except TRMNLError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err
        return {device.mac_address: device for device in devices}

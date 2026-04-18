"""Define an object to manage fetching TRMNL data."""

from __future__ import annotations

from datetime import timedelta

from trmnl import TRMNLClient
from trmnl.exceptions import TRMNLAuthenticationError, TRMNLError
from trmnl.models import Device

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type TRMNLConfigEntry = ConfigEntry[TRMNLCoordinator]


class TRMNLCoordinator(DataUpdateCoordinator[dict[int, Device]]):
    """Class to manage fetching TRMNL data."""

    config_entry: TRMNLConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: TRMNLConfigEntry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(hours=1),
        )
        self.client = TRMNLClient(
            token=config_entry.data[CONF_API_KEY],
            session=async_get_clientsession(hass),
        )

    async def _async_update_data(self) -> dict[int, Device]:
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
        new_data = {device.identifier: device for device in devices}
        if self.data is not None:
            device_registry = dr.async_get(self.hass)
            for device_id in set(self.data) - set(new_data):
                if entry := device_registry.async_get_device(
                    identifiers={(DOMAIN, str(device_id))}
                ):
                    device_registry.async_update_device(
                        device_id=entry.id,
                        remove_config_entry_id=self.config_entry.entry_id,
                    )
        return new_data

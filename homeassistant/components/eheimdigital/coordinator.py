"""Data update coordinator for the EHEIM Digital integration."""

import aiohttp
from eheimdigital.device import EheimDigitalDevice
from eheimdigital.hub import EheimDigitalHub

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER


class EheimDigitalUpdateCoordinator(
    DataUpdateCoordinator[dict[str, EheimDigitalDevice]]
):
    """The EHEIM Digital data update coordinator."""

    hub: EheimDigitalHub
    device_infos: dict[str, DeviceInfo]
    session: aiohttp.ClientSession

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the EHEIM Digital data update coordinator."""
        super().__init__(
            hass, LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL
        )
        self.session = async_create_clientsession(
            hass, base_url=f"http://{config_entry.data[CONF_HOST]}"
        )

        self.hub = EheimDigitalHub(
            session=self.session,
            loop=hass.loop,
            receive_callback=self._async_receive_callback,
        )

    async def _async_receive_callback(self) -> None:
        self.async_set_updated_data(self.hub.devices)  # pragma: no cover

    async def _async_setup(self) -> None:
        await self.hub.connect()
        await self.hub.update()

    async def _async_update_data(self) -> dict[str, EheimDigitalDevice]:
        await self.hub.update()
        return self.data

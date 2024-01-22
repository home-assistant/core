"""The ATAG Integration."""
from asyncio import timeout
from datetime import timedelta
import logging

from pyatag import AtagException, AtagOne

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "atag"
PLATFORMS = [Platform.CLIMATE, Platform.WATER_HEATER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Atag integration from a config entry."""

    async def _async_update_data():
        """Update data via library."""
        async with timeout(20):
            try:
                await atag.update()
            except AtagException as err:
                raise UpdateFailed(err) from err
        return atag

    atag = AtagOne(
        session=async_get_clientsession(hass), **entry.data, device=entry.unique_id
    )
    coordinator = DataUpdateCoordinator[AtagOne](
        hass,
        _LOGGER,
        name=DOMAIN.title(),
        update_method=_async_update_data,
        update_interval=timedelta(seconds=60),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=atag.id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Atag config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class AtagEntity(CoordinatorEntity[DataUpdateCoordinator[AtagOne]]):
    """Defines a base Atag entity."""

    def __init__(
        self, coordinator: DataUpdateCoordinator[AtagOne], atag_id: str
    ) -> None:
        """Initialize the Atag entity."""
        super().__init__(coordinator)

        self._id = atag_id
        self._attr_name = DOMAIN.title()
        self._attr_unique_id = f"{coordinator.data.id}-{atag_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return info for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data.id)},
            manufacturer="Atag",
            model="Atag One",
            name="Atag Thermostat",
            sw_version=self.coordinator.data.apiversion,
        )

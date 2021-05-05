"""Support for WLED."""
from __future__ import annotations

from datetime import timedelta
import logging

from wled import WLED, Device as WLEDDevice, WLEDConnectionError, WLEDError

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
    CONF_HOST,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=5)
PLATFORMS = (LIGHT_DOMAIN, SENSOR_DOMAIN, SWITCH_DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WLED from a config entry."""

    # Create WLED instance for this entry
    coordinator = WLEDDataUpdateCoordinator(hass, host=entry.data[CONF_HOST])
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # For backwards compat, set unique ID
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry, unique_id=coordinator.data.info.mac_address
        )

    # Set up all platforms for this device/entry.
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload WLED config entry."""

    # Unload entities for this entry/device.
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]

    if not hass.data[DOMAIN]:
        del hass.data[DOMAIN]

    return unload_ok


def wled_exception_handler(func):
    """Decorate WLED calls to handle WLED exceptions.

    A decorator that wraps the passed in function, catches WLED errors,
    and handles the availability of the device in the data coordinator.
    """

    async def handler(self, *args, **kwargs):
        try:
            await func(self, *args, **kwargs)
            self.coordinator.update_listeners()

        except WLEDConnectionError as error:
            _LOGGER.error("Error communicating with API: %s", error)
            self.coordinator.last_update_success = False
            self.coordinator.update_listeners()

        except WLEDError as error:
            _LOGGER.error("Invalid response from API: %s", error)

    return handler


class WLEDDataUpdateCoordinator(DataUpdateCoordinator[WLEDDevice]):
    """Class to manage fetching WLED data from single endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        host: str,
    ):
        """Initialize global WLED data updater."""
        self.wled = WLED(host, session=async_get_clientsession(hass))

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    def update_listeners(self) -> None:
        """Call update on all listeners."""
        for update_callback in self._listeners:
            update_callback()

    async def _async_update_data(self) -> WLEDDevice:
        """Fetch data from WLED."""
        try:
            return await self.wled.update(full_update=not self.last_update_success)
        except WLEDError as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error


class WLEDEntity(CoordinatorEntity[WLEDDevice]):
    """Defines a base WLED entity."""

    coordinator: WLEDDataUpdateCoordinator

    def __init__(
        self,
        *,
        entry_id: str,
        coordinator: WLEDDataUpdateCoordinator,
        name: str,
        icon: str,
        enabled_default: bool = True,
    ) -> None:
        """Initialize the WLED entity."""
        super().__init__(coordinator)
        self._enabled_default = enabled_default
        self._entry_id = entry_id
        self._icon = icon
        self._name = name
        self._unsub_dispatcher = None

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        return self._icon

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default


class WLEDDeviceEntity(WLEDEntity):
    """Defines a WLED device entity."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this WLED device."""
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self.coordinator.data.info.mac_address)},
            ATTR_NAME: self.coordinator.data.info.name,
            ATTR_MANUFACTURER: self.coordinator.data.info.brand,
            ATTR_MODEL: self.coordinator.data.info.product,
            ATTR_SW_VERSION: self.coordinator.data.info.version,
        }

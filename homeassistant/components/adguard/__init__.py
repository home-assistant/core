"""Support for AdGuard Home."""
from __future__ import annotations

import logging

from adguardhome import AdGuardHome, AdGuardHomeConnectionError, AdGuardHomeError
import voluptuous as vol

from homeassistant.components.adguard.const import (
    CONF_FORCE,
    DATA_ADGUARD_CLIENT,
    DATA_ADGUARD_VERSION,
    DOMAIN,
    SERVICE_ADD_URL,
    SERVICE_DISABLE_URL,
    SERVICE_ENABLE_URL,
    SERVICE_REFRESH,
    SERVICE_REMOVE_URL,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo, Entity

_LOGGER = logging.getLogger(__name__)

SERVICE_URL_SCHEMA = vol.Schema({vol.Required(CONF_URL): cv.url})
SERVICE_ADD_URL_SCHEMA = vol.Schema(
    {vol.Required(CONF_NAME): cv.string, vol.Required(CONF_URL): cv.url}
)
SERVICE_REFRESH_SCHEMA = vol.Schema(
    {vol.Optional(CONF_FORCE, default=False): cv.boolean}
)

PLATFORMS = ["sensor", "switch"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AdGuard Home from a config entry."""
    session = async_get_clientsession(hass, entry.data[CONF_VERIFY_SSL])
    adguard = AdGuardHome(
        entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        tls=entry.data[CONF_SSL],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
        session=session,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_ADGUARD_CLIENT: adguard}

    try:
        await adguard.version()
    except AdGuardHomeConnectionError as exception:
        raise ConfigEntryNotReady from exception

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async def add_url(call) -> None:
        """Service call to add a new filter subscription to AdGuard Home."""
        await adguard.filtering.add_url(
            allowlist=False, name=call.data.get(CONF_NAME), url=call.data.get(CONF_URL)
        )

    async def remove_url(call) -> None:
        """Service call to remove a filter subscription from AdGuard Home."""
        await adguard.filtering.remove_url(allowlist=False, url=call.data.get(CONF_URL))

    async def enable_url(call) -> None:
        """Service call to enable a filter subscription in AdGuard Home."""
        await adguard.filtering.enable_url(allowlist=False, url=call.data.get(CONF_URL))

    async def disable_url(call) -> None:
        """Service call to disable a filter subscription in AdGuard Home."""
        await adguard.filtering.disable_url(
            allowlist=False, url=call.data.get(CONF_URL)
        )

    async def refresh(call) -> None:
        """Service call to refresh the filter subscriptions in AdGuard Home."""
        await adguard.filtering.refresh(
            allowlist=False, force=call.data.get(CONF_FORCE)
        )

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_URL, add_url, schema=SERVICE_ADD_URL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_URL, remove_url, schema=SERVICE_URL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ENABLE_URL, enable_url, schema=SERVICE_URL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DISABLE_URL, disable_url, schema=SERVICE_URL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH, refresh, schema=SERVICE_REFRESH_SCHEMA
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload AdGuard Home config entry."""
    hass.services.async_remove(DOMAIN, SERVICE_ADD_URL)
    hass.services.async_remove(DOMAIN, SERVICE_REMOVE_URL)
    hass.services.async_remove(DOMAIN, SERVICE_ENABLE_URL)
    hass.services.async_remove(DOMAIN, SERVICE_DISABLE_URL)
    hass.services.async_remove(DOMAIN, SERVICE_REFRESH)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        del hass.data[DOMAIN]

    return unload_ok


class AdGuardHomeEntity(Entity):
    """Defines a base AdGuard Home entity."""

    def __init__(
        self,
        adguard: AdGuardHome,
        entry: ConfigEntry,
        name: str,
        icon: str,
        enabled_default: bool = True,
    ) -> None:
        """Initialize the AdGuard Home entity."""
        self._available = True
        self._enabled_default = enabled_default
        self._icon = icon
        self._name = name
        self._entry = entry
        self.adguard = adguard

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

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    async def async_update(self) -> None:
        """Update AdGuard Home entity."""
        if not self.enabled:
            return

        try:
            await self._adguard_update()
            self._available = True
        except AdGuardHomeError:
            if self._available:
                _LOGGER.debug(
                    "An error occurred while updating AdGuard Home sensor",
                    exc_info=True,
                )
            self._available = False

    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        raise NotImplementedError()


class AdGuardHomeDeviceEntity(AdGuardHomeEntity):
    """Defines a AdGuard Home device entity."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this AdGuard Home instance."""
        return {
            "identifiers": {
                (DOMAIN, self.adguard.host, self.adguard.port, self.adguard.base_path)
            },
            "name": "AdGuard Home",
            "manufacturer": "AdGuard Team",
            "sw_version": self.hass.data[DOMAIN][self._entry.entry_id].get(
                DATA_ADGUARD_VERSION
            ),
            "entry_type": "service",
        }

"""Support for AdGuard Home."""
from distutils.version import LooseVersion
import logging
from typing import Any, Dict

from adguardhome import AdGuardHome, AdGuardHomeConnectionError, AdGuardHomeError
import voluptuous as vol

from homeassistant.components.adguard.const import (
    CONF_FORCE,
    DATA_ADGUARD_CLIENT,
    DATA_ADGUARD_VERION,
    DOMAIN,
    MIN_ADGUARD_HOME_VERSION,
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
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

_LOGGER = logging.getLogger(__name__)

SERVICE_URL_SCHEMA = vol.Schema({vol.Required(CONF_URL): cv.url})
SERVICE_ADD_URL_SCHEMA = vol.Schema(
    {vol.Required(CONF_NAME): cv.string, vol.Required(CONF_URL): cv.url}
)
SERVICE_REFRESH_SCHEMA = vol.Schema(
    {vol.Optional(CONF_FORCE, default=False): cv.boolean}
)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the AdGuard Home components."""
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
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

    hass.data.setdefault(DOMAIN, {})[DATA_ADGUARD_CLIENT] = adguard

    try:
        version = await adguard.version()
    except AdGuardHomeConnectionError as exception:
        raise ConfigEntryNotReady from exception

    if version and LooseVersion(MIN_ADGUARD_HOME_VERSION) > LooseVersion(version):
        _LOGGER.error(
            "This integration requires AdGuard Home v0.99.0 or higher to work correctly"
        )
        raise ConfigEntryNotReady

    for component in "sensor", "switch":
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    async def add_url(call) -> None:
        """Service call to add a new filter subscription to AdGuard Home."""
        await adguard.filtering.add_url(
            call.data.get(CONF_NAME), call.data.get(CONF_URL)
        )

    async def remove_url(call) -> None:
        """Service call to remove a filter subscription from AdGuard Home."""
        await adguard.filtering.remove_url(call.data.get(CONF_URL))

    async def enable_url(call) -> None:
        """Service call to enable a filter subscription in AdGuard Home."""
        await adguard.filtering.enable_url(call.data.get(CONF_URL))

    async def disable_url(call) -> None:
        """Service call to disable a filter subscription in AdGuard Home."""
        await adguard.filtering.disable_url(call.data.get(CONF_URL))

    async def refresh(call) -> None:
        """Service call to refresh the filter subscriptions in AdGuard Home."""
        await adguard.filtering.refresh(call.data.get(CONF_FORCE))

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


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigType) -> bool:
    """Unload AdGuard Home config entry."""
    hass.services.async_remove(DOMAIN, SERVICE_ADD_URL)
    hass.services.async_remove(DOMAIN, SERVICE_REMOVE_URL)
    hass.services.async_remove(DOMAIN, SERVICE_ENABLE_URL)
    hass.services.async_remove(DOMAIN, SERVICE_DISABLE_URL)
    hass.services.async_remove(DOMAIN, SERVICE_REFRESH)

    for component in "sensor", "switch":
        await hass.config_entries.async_forward_entry_unload(entry, component)

    del hass.data[DOMAIN]

    return True


class AdGuardHomeEntity(Entity):
    """Defines a base AdGuard Home entity."""

    def __init__(
        self, adguard, name: str, icon: str, enabled_default: bool = True
    ) -> None:
        """Initialize the AdGuard Home entity."""
        self._available = True
        self._enabled_default = enabled_default
        self._icon = icon
        self._name = name
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
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this AdGuard Home instance."""
        return {
            "identifiers": {
                (DOMAIN, self.adguard.host, self.adguard.port, self.adguard.base_path)
            },
            "name": "AdGuard Home",
            "manufacturer": "AdGuard Team",
            "sw_version": self.hass.data[DOMAIN].get(DATA_ADGUARD_VERION),
            "entry_type": "service",
        }

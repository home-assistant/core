"""Support for AdGuard Home."""

from dataclasses import dataclass

from adguardhome import AdGuardHome, AdGuardHomeConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_FORCE,
    DOMAIN,
    SERVICE_ADD_URL,
    SERVICE_DISABLE_URL,
    SERVICE_ENABLE_URL,
    SERVICE_GET_URL_ENABLED,
    SERVICE_REFRESH,
    SERVICE_REMOVE_URL,
)

SERVICE_URL_SCHEMA = vol.Schema({vol.Required(CONF_URL): vol.Any(cv.url, cv.path)})
SERVICE_URL_ENABLED_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(CONF_URL): vol.Any(cv.url, cv.path),
    }
)
SERVICE_ADD_URL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_URL): vol.Any(cv.url, cv.path),
    }
)
SERVICE_REFRESH_SCHEMA = vol.Schema(
    {vol.Optional(CONF_FORCE, default=False): cv.boolean}
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.SENSOR, Platform.SWITCH, Platform.UPDATE]
type AdGuardConfigEntry = ConfigEntry[AdGuardData]


@dataclass
class AdGuardData:
    """Adguard data type."""

    client: AdGuardHome
    version: str


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""

    def _get_adguard_config_entries(hass: HomeAssistant) -> list[AdGuardConfigEntry]:
        """Get the AdGuardHome config entries."""
        entries: list[AdGuardConfigEntry] = hass.config_entries.async_loaded_entries(
            DOMAIN
        )
        if not entries:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="config_entry_not_loaded"
            )
        return entries

    def _get_adguard_instances(hass: HomeAssistant) -> list[AdGuardHome]:
        """Get the AdGuardHome instances."""
        entries = _get_adguard_config_entries(hass)
        return [entry.runtime_data.client for entry in entries]

    def _get_adguard_device_instance(
        hass: HomeAssistant, device_id: str
    ) -> AdGuardHome:
        """Get the AdGuardHome instance for a device."""
        device_registry = dr.async_get(hass)
        device_entry = device_registry.async_get(device_id)
        if device_entry is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_device_id",
                translation_placeholders={"device_id": device_id},
            )
        entry = next(
            (
                entry
                for entry in _get_adguard_config_entries(hass)
                if entry.entry_id in device_entry.config_entries
            ),
            None,
        )
        if entry is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="config_entry_not_loaded"
            )
        return entry.runtime_data.client

    async def add_url(call: ServiceCall) -> None:
        """Service call to add a new filter subscription to AdGuard Home."""
        for adguard in _get_adguard_instances(call.hass):
            await adguard.filtering.add_url(
                allowlist=False, name=call.data[CONF_NAME], url=call.data[CONF_URL]
            )

    async def remove_url(call: ServiceCall) -> None:
        """Service call to remove a filter subscription from AdGuard Home."""
        for adguard in _get_adguard_instances(call.hass):
            await adguard.filtering.remove_url(allowlist=False, url=call.data[CONF_URL])

    async def enable_url(call: ServiceCall) -> None:
        """Service call to enable a filter subscription in AdGuard Home."""
        for adguard in _get_adguard_instances(call.hass):
            await adguard.filtering.enable_url(allowlist=False, url=call.data[CONF_URL])

    async def url_enabled(call: ServiceCall) -> ServiceResponse:
        """Service call to check if a filter subscription is enabled in AdGuard Home."""
        adguard = _get_adguard_device_instance(
            call.hass, device_id=call.data[ATTR_DEVICE_ID]
        )
        return {
            "enabled": await adguard.filtering.url_enabled(
                allowlist=False, url=call.data[CONF_URL]
            )
        }

    async def disable_url(call: ServiceCall) -> None:
        """Service call to disable a filter subscription in AdGuard Home."""
        for adguard in _get_adguard_instances(call.hass):
            await adguard.filtering.disable_url(
                allowlist=False, url=call.data[CONF_URL]
            )

    async def refresh(call: ServiceCall) -> None:
        """Service call to refresh the filter subscriptions in AdGuard Home."""
        for adguard in _get_adguard_instances(call.hass):
            await adguard.filtering.refresh(
                allowlist=False, force=call.data[CONF_FORCE]
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
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_URL_ENABLED,
        url_enabled,
        schema=SERVICE_URL_ENABLED_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AdGuardConfigEntry) -> bool:
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

    try:
        version = await adguard.version()
    except AdGuardHomeConnectionError as exception:
        raise ConfigEntryNotReady from exception

    entry.runtime_data = AdGuardData(adguard, version)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AdGuardConfigEntry) -> bool:
    """Unload AdGuard Home config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

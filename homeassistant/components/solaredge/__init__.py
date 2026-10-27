"""The SolarEdge integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_TOKEN, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import config_entry_oauth2_flow, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    SolarEdgeApiError,
    SolarEdgeAuthError,
    SolarEdgeRateLimitError,
    SolarEdgeV2,
)
from .const import CONF_SITE_ID, DATA_API_CLIENT, DATA_MODULES_COORDINATOR, DOMAIN
from .coordinator import SolarEdgeModulesCoordinator
from .types import SolarEdgeConfigEntry, SolarEdgeData

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SolarEdgeConfigEntry) -> None:
    """Set up SolarEdge from a config entry."""
    entry.runtime_data = SolarEdgeData()
    site_id = entry.data[CONF_SITE_ID]

    if CONF_TOKEN in entry.data:
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, entry
            )
        )
        oauth_session = config_entry_oauth2_flow.OAuth2Session(
            hass, entry, implementation
        )

        async def async_get_access_token() -> str:
            await oauth_session.async_ensure_token_valid()
            return oauth_session.token["access_token"]

        api = SolarEdgeV2(async_get_clientsession(hass), async_get_access_token)
        try:
            response = await api.get_details(site_id)
        except SolarEdgeAuthError as ex:
            raise ConfigEntryAuthFailed from ex
        except SolarEdgeRateLimitError as ex:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key=(
                    "monthly_credit_limit" if ex.monthly_limit else "rate_limit"
                ),
            ) from ex
        except SolarEdgeApiError as ex:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_retrieve_details",
            ) from ex

        if "details" not in response:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="missing_details",
            )

        if response["details"].get("status", "").lower() != "active":
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="site_not_active",
            )

        entry.runtime_data[DATA_API_CLIENT] = api

        # Register the site device up front so per-battery devices can resolve it
        # as their via_device when their entities are created.
        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, site_id)},
            manufacturer="SolarEdge",
        )

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    elif CONF_API_KEY in entry.data:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="oauth_migration_required",
        )

    # Setup for username/password (modules statistics)
    if CONF_USERNAME in entry.data:
        coordinator = SolarEdgeModulesCoordinator(hass, entry)
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data[DATA_MODULES_COORDINATOR] = coordinator


async def async_unload_entry(hass: HomeAssistant, entry: SolarEdgeConfigEntry) -> None:
    """Unload SolarEdge config entry."""
    if DATA_API_CLIENT not in entry.runtime_data:
        return  # Nothing to unload

    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate legacy API-key entries to the OAuth-capable entry version."""
    if config_entry.version == 1:
        hass.config_entries.async_update_entry(
            config_entry,
            unique_id=config_entry.unique_id or config_entry.data[CONF_SITE_ID],
            version=2,
        )
    return True

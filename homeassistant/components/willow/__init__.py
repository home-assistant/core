"""The Willow integration."""

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from . import api
from .client import WillowClient
from .const import (
    DOMAIN,
    OAUTH2_CLIENT_ID,
    OAUTH2_CLIENT_SECRET,
    PANEL_FILE,
    PANEL_ICON,
    PANEL_NAME,
    PANEL_STATIC_PATH,
    PANEL_TITLE,
    PANEL_URL_PATH,
)
from .coordinator import WillowDataUpdateCoordinator

_PLATFORMS: list[Platform] = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type WillowConfigEntry = ConfigEntry[api.WillowRuntimeData]

_PANEL_REGISTERED = "panel_registered"
_STATIC_REGISTERED = "static_registered"


async def _async_register_panel(hass: HomeAssistant) -> None:
    """Register the Willow sidebar panel and its frontend assets."""
    domain_data = hass.data.setdefault(DOMAIN, {})

    if not domain_data.get(_STATIC_REGISTERED):
        frontend_dir = Path(__file__).parent / "frontend"
        await hass.http.async_register_static_paths(
            [StaticPathConfig(PANEL_STATIC_PATH, str(frontend_dir), True)]
        )
        domain_data[_STATIC_REGISTERED] = True

    if domain_data.get(_PANEL_REGISTERED):
        return

    integration = await async_get_integration(hass, DOMAIN)
    module_url = f"{PANEL_STATIC_PATH}/{PANEL_FILE}?v={integration.version}"

    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_NAME,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        module_url=module_url,
        embed_iframe=False,
        require_admin=False,
    )
    domain_data[_PANEL_REGISTERED] = True


def _async_unregister_panel(hass: HomeAssistant) -> None:
    """Remove the Willow sidebar panel."""
    domain_data = hass.data.get(DOMAIN, {})
    if not domain_data.get(_PANEL_REGISTERED):
        return
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
    domain_data[_PANEL_REGISTERED] = False


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Willow integration."""
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET, name="Willow"),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: WillowConfigEntry) -> bool:
    """Set up Willow from a config entry."""
    try:
        implementation = await async_get_config_entry_implementation(hass, entry)
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            "OAuth2 implementation temporarily unavailable, will retry"
        ) from err

    session = OAuth2Session(hass, entry, implementation)
    await session.async_ensure_token_valid()

    client = WillowClient(
        aiohttp_client.async_get_clientsession(hass),
        session.token[CONF_ACCESS_TOKEN],
    )
    coordinator = WillowDataUpdateCoordinator(
        hass,
        entry,
        client,
        session,
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = api.WillowRuntimeData(
        coordinator=coordinator,
        profile=coordinator.profile,
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    await _async_register_panel(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WillowConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)

    if unload_ok and not hass.config_entries.async_loaded_entries(DOMAIN):
        _async_unregister_panel(hass)

    return unload_ok

"""The Willow integration."""

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import CONF_ACCESS_TOKEN, Platform, __version__ as HA_VERSION
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
from .coordinator import WillowConfigEntry, WillowDataUpdateCoordinator

_PLATFORMS: list[Platform] = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


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

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    await _async_register_panel(hass)

    return True


async def _async_register_panel(hass: HomeAssistant) -> None:
    """Register the Willow sidebar panel and its frontend assets."""
    if frontend.async_panel_exists(hass, PANEL_URL_PATH):
        return

    frontend_dir = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(PANEL_STATIC_PATH, str(frontend_dir), True)]
    )

    integration = await async_get_integration(hass, DOMAIN)
    version = integration.version or HA_VERSION
    module_url = f"{PANEL_STATIC_PATH}/{PANEL_FILE}?v={version}"

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


def _async_unregister_panel(hass: HomeAssistant) -> None:
    """Remove the Willow sidebar panel."""
    frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)


async def async_unload_entry(hass: HomeAssistant, entry: WillowConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)

    if unload_ok and not hass.config_entries.async_loaded_entries(DOMAIN):
        _async_unregister_panel(hass)

    return unload_ok

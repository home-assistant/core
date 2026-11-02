"""Provide Home Assistant app management."""

from urllib.parse import urlsplit

from homeassistant.components.hassio import (
    AddonManager,
    HassioNotReadyError,
    get_addons_info,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.hassio import is_hassio
from homeassistant.helpers.singleton import singleton

from .const import APP_NAME, APP_SLUG, DOMAIN, LOGGER

DATA_APP_MANAGER = f"{DOMAIN}_app_manager"


@callback
def async_check_app_running(hass: HomeAssistant, url: str) -> None:
    """Explain connection failures when the configured local app is offline."""
    if not is_hassio(hass):
        return

    try:
        apps = get_addons_info(hass)
    except HassioNotReadyError:
        return

    hostname = urlsplit(url).hostname
    for info in apps.values():
        if (
            info is not None
            and info["hostname"] == hostname
            and info["state"] in ("stopped", "error", "startup")
        ):
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="app_not_running",
                translation_placeholders={"app": info["name"]},
            )


@singleton(DATA_APP_MANAGER)
@callback
def get_app_manager(hass: HomeAssistant) -> AddonManager:
    """Get the app manager."""
    return AddonManager(hass, LOGGER, APP_NAME, APP_SLUG)

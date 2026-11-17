"""Services for the frontend integration."""

from enum import StrEnum
import logging

import probatio

from homeassistant.config import async_hass_config_yaml
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import service

from .const import DOMAIN
from .helpers import (
    CONF_THEMES,
    DATA_DEFAULT_DARK_THEME,
    DATA_DEFAULT_THEME,
    DATA_THEMES,
    DATA_THEMES_STORE,
    DEFAULT_THEME,
    THEMES_SAVE_DELAY,
    VALUE_NO_THEME,
    async_update_theme_and_fire_event,
    validate_selected_theme,
    validate_themes,
)

_LOGGER = logging.getLogger(__package__)


class FrontendService(StrEnum):
    """Store keys for frontend services."""

    RELOAD_THEMES = "reload_themes"
    SET_THEME = "set_theme"


class FrontendServiceArgument(StrEnum):
    """Store keys for frontend service arguments."""

    MODE = "mode"
    NAME = "name"
    NAME_DARK = "name_dark"


@callback
def _set_theme(call: ServiceCall) -> None:
    """Set backend-preferred theme."""
    hass = call.hass

    def _update_hass_theme(theme: str, light: bool) -> None:
        theme_key = DATA_DEFAULT_THEME if light else DATA_DEFAULT_DARK_THEME
        if theme == VALUE_NO_THEME:
            to_set = DEFAULT_THEME if light else None
        else:
            _LOGGER.info(
                "Theme %s set as default %s theme",
                theme,
                "light" if light else "dark",
            )
            to_set = theme
        hass.data[theme_key] = to_set

    name = call.data.get(FrontendServiceArgument.NAME)
    if name is not None and FrontendServiceArgument.MODE in call.data:
        mode = call.data.get(FrontendServiceArgument.MODE, "light")
        light_mode = mode == "light"
        _update_hass_theme(name, light_mode)
    else:
        name_dark = call.data.get(FrontendServiceArgument.NAME_DARK)
        if name:
            _update_hass_theme(name, True)
        if name_dark:
            _update_hass_theme(name_dark, False)

    hass.data[DATA_THEMES_STORE].async_delay_save(
        lambda: {
            DATA_DEFAULT_THEME: hass.data[DATA_DEFAULT_THEME],
            DATA_DEFAULT_DARK_THEME: hass.data.get(DATA_DEFAULT_DARK_THEME),
        },
        THEMES_SAVE_DELAY,
    )
    async_update_theme_and_fire_event(hass)


async def _reload_themes(call: ServiceCall) -> None:
    """Reload themes."""
    hass = call.hass
    config = await async_hass_config_yaml(hass)
    new_themes = config.get(DOMAIN, {}).get(CONF_THEMES, {})

    try:
        new_themes = validate_themes(new_themes)
    except probatio.Invalid as err:
        raise HomeAssistantError(f"Failed to reload themes: {err}") from err

    hass.data[DATA_THEMES] = new_themes
    if hass.data[DATA_DEFAULT_THEME] not in new_themes:
        hass.data[DATA_DEFAULT_THEME] = DEFAULT_THEME
    if (
        hass.data.get(DATA_DEFAULT_DARK_THEME)
        and hass.data.get(DATA_DEFAULT_DARK_THEME) not in new_themes
    ):
        hass.data[DATA_DEFAULT_DARK_THEME] = None
    async_update_theme_and_fire_event(hass)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the frontend services."""
    service.async_register_admin_service(
        hass,
        DOMAIN,
        FrontendService.SET_THEME,
        _set_theme,
        probatio.All(
            {
                probatio.Optional(
                    FrontendServiceArgument.NAME
                ): validate_selected_theme,
                probatio.Exclusive(
                    FrontendServiceArgument.NAME_DARK, "dark_modes"
                ): validate_selected_theme,
                probatio.Exclusive(
                    FrontendServiceArgument.MODE, "dark_modes"
                ): probatio.Any("dark", "light"),
            },
            probatio.AtLeastOne(
                FrontendServiceArgument.NAME, FrontendServiceArgument.NAME_DARK
            ),
        ),
    )

    service.async_register_admin_service(
        hass, DOMAIN, FrontendService.RELOAD_THEMES, _reload_themes
    )

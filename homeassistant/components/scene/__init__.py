"""Allow users to set and activate scenes."""

import importlib
import logging
from typing import Any, Final

import probatio

from homeassistant.components.light import ATTR_TRANSITION
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PLATFORM, SERVICE_TURN_ON
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import DATA_COMPONENT, DOMAIN
from .entity import BaseScene, Scene
from .services import async_setup_services

STATES: Final = "states"


def _hass_domain_validator(config: dict[str, Any]) -> dict[str, Any]:
    """Validate platform in config for homeassistant domain."""
    if CONF_PLATFORM not in config:
        config = {CONF_PLATFORM: HOMEASSISTANT_DOMAIN, STATES: config}

    return config


def _platform_validator(config: dict[str, Any]) -> dict[str, Any]:
    """Validate it is a valid  platform."""
    platform_name = config[CONF_PLATFORM]
    try:
        platform = importlib.import_module(
            f"homeassistant.components.{platform_name}.scene"
        )
    except ImportError:
        raise probatio.Invalid("Invalid platform specified") from None

    if not hasattr(platform, "PLATFORM_SCHEMA"):
        return config

    return platform.PLATFORM_SCHEMA(config)  # type: ignore[no-any-return]


PLATFORM_SCHEMA = probatio.Schema(
    probatio.All(
        _hass_domain_validator,
        probatio.Schema(
            {probatio.Required(CONF_PLATFORM): str}, extra=probatio.ALLOW_EXTRA
        ),
        _platform_validator,
    ),
    extra=probatio.ALLOW_EXTRA,
)

__all__ = [
    "ATTR_TRANSITION",
    "DOMAIN",
    "PLATFORM_SCHEMA",
    "SERVICE_TURN_ON",
    "STATES",
    "BaseScene",
    "Scene",
]

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the scenes."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[BaseScene](
        logging.getLogger(__name__), DOMAIN, hass
    )

    await component.async_setup(config)
    # Ensure Home Assistant platform always loaded.
    hass.async_create_task(
        component.async_setup_platform(
            HOMEASSISTANT_DOMAIN, {"platform": HOMEASSISTANT_DOMAIN, STATES: []}
        ),
        eager_start=True,
    )
    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)

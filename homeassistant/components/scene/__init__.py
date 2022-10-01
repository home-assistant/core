"""Allow users to set and activate scenes."""
from __future__ import annotations

import functools as ft
import importlib
import logging
from typing import Any, Final, final

import voluptuous as vol

from homeassistant.components.light import ATTR_TRANSITION
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PLATFORM, SERVICE_TURN_ON, STATE_UNAVAILABLE
from homeassistant.core import DOMAIN as HA_DOMAIN, HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

DOMAIN: Final = "scene"
STATES: Final = "states"


def _hass_domain_validator(config: dict[str, Any]) -> dict[str, Any]:
    """Validate platform in config for homeassistant domain."""
    if CONF_PLATFORM not in config:
        config = {CONF_PLATFORM: HA_DOMAIN, STATES: config}

    return config


def _platform_validator(config: dict[str, Any]) -> dict[str, Any]:
    """Validate it is a valid  platform."""
    try:
        platform = importlib.import_module(f".{config[CONF_PLATFORM]}", __name__)
    except ImportError:
        try:
            platform = importlib.import_module(
                f"homeassistant.components.{config[CONF_PLATFORM]}.scene"
            )
        except ImportError:
            raise vol.Invalid("Invalid platform specified") from None

    if not hasattr(platform, "PLATFORM_SCHEMA"):
        return config

    return platform.PLATFORM_SCHEMA(config)  # type: ignore[no-any-return]


PLATFORM_SCHEMA = vol.Schema(
    vol.All(
        _hass_domain_validator,
        vol.Schema({vol.Required(CONF_PLATFORM): str}, extra=vol.ALLOW_EXTRA),
        _platform_validator,
    ),
    extra=vol.ALLOW_EXTRA,
)

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the scenes."""
    component = hass.data[DOMAIN] = EntityComponent[Scene](
        logging.getLogger(__name__), DOMAIN, hass
    )

    await component.async_setup(config)
    # Ensure Home Assistant platform always loaded.
    await component.async_setup_platform(HA_DOMAIN, {"platform": HA_DOMAIN, STATES: []})
    component.async_register_entity_service(
        SERVICE_TURN_ON,
        {ATTR_TRANSITION: vol.All(vol.Coerce(float), vol.Clamp(min=0, max=6553))},
        "_async_activate",
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[Scene] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[Scene] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


class Scene(RestoreEntity):
    """A scene is a group of entities and the states we want them to be."""

    _attr_should_poll = False
    __last_activated: str | None = None

    @property
    @final
    def state(self) -> str | None:
        """Return the state of the scene."""
        if self.__last_activated is None:
            return None
        return self.__last_activated

    @final
    async def _async_activate(self, **kwargs: Any) -> None:
        """Activate scene.

        Should not be overridden, handle setting last press timestamp.
        """
        self.__last_activated = dt_util.utcnow().isoformat()
        self.async_write_ha_state()
        await self.async_activate(**kwargs)

    async def async_internal_added_to_hass(self) -> None:
        """Call when the scene is added to hass."""
        await super().async_internal_added_to_hass()
        state = await self.async_get_last_state()
        if (
            state is not None
            and state.state is not None
            and state.state != STATE_UNAVAILABLE
        ):
            self.__last_activated = state.state

    def activate(self, **kwargs: Any) -> None:
        """Activate scene. Try to get entities into requested state."""
        raise NotImplementedError()

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate scene. Try to get entities into requested state."""
        task = self.hass.async_add_job(ft.partial(self.activate, **kwargs))
        if task:
            await task

"""Component to interface with various sirens/chimes."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any, TypedDict, cast, final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SERVICE_TOGGLE, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import ToggleEntity, ToggleEntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_AVAILABLE_TONES,
    ATTR_DURATION,
    ATTR_TONE,
    ATTR_VOLUME_LEVEL,
    DOMAIN,
    SUPPORT_DURATION,
    SUPPORT_TONES,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_SET,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)

TURN_ON_SCHEMA = {
    vol.Optional(ATTR_TONE): vol.Any(vol.Coerce(int), cv.string),
    vol.Optional(ATTR_DURATION): cv.positive_int,
    vol.Optional(ATTR_VOLUME_LEVEL): cv.small_float,
}


class SirenTurnOnServiceParameters(TypedDict, total=False):
    """Represent possible parameters to siren.turn_on service data dict type."""

    tone: int | str
    duration: int
    volume_level: float


def process_turn_on_params(
    siren: SirenEntity, params: SirenTurnOnServiceParameters
) -> SirenTurnOnServiceParameters:
    """
    Process turn_on service params.

    Filters out unsupported params and validates the rest.
    """
    supported_features = siren.supported_features or 0

    if not supported_features & SUPPORT_TONES:
        params.pop(ATTR_TONE, None)
    elif (tone := params.get(ATTR_TONE)) is not None and (
        not siren.available_tones or tone not in siren.available_tones
    ):
        raise ValueError(f"Invalid tone received for entity {siren.entity_id}: {tone}")

    if not supported_features & SUPPORT_DURATION:
        params.pop(ATTR_DURATION, None)
    if not supported_features & SUPPORT_VOLUME_SET:
        params.pop(ATTR_VOLUME_LEVEL, None)

    return params


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up siren devices."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    async def async_handle_turn_on_service(
        siren: SirenEntity, call: ServiceCall
    ) -> None:
        """Handle turning a siren on."""
        data = {
            k: v
            for k, v in call.data.items()
            if k in (ATTR_TONE, ATTR_DURATION, ATTR_VOLUME_LEVEL)
        }
        await siren.async_turn_on(
            **process_turn_on_params(siren, cast(SirenTurnOnServiceParameters, data))
        )

    component.async_register_entity_service(
        SERVICE_TURN_ON, TURN_ON_SCHEMA, async_handle_turn_on_service, [SUPPORT_TURN_ON]
    )
    component.async_register_entity_service(
        SERVICE_TURN_OFF, {}, "async_turn_off", [SUPPORT_TURN_OFF]
    )
    component.async_register_entity_service(
        SERVICE_TOGGLE, {}, "async_toggle", [SUPPORT_TURN_ON & SUPPORT_TURN_OFF]
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


@dataclass
class SirenEntityDescription(ToggleEntityDescription):
    """A class that describes siren entities."""


class SirenEntity(ToggleEntity):
    """Representation of a siren device."""

    entity_description: SirenEntityDescription
    _attr_available_tones: list[int | str] | None = None

    @final
    @property
    def capability_attributes(self) -> dict[str, Any] | None:
        """Return capability attributes."""
        supported_features = self.supported_features or 0

        if supported_features & SUPPORT_TONES and self.available_tones is not None:
            return {ATTR_AVAILABLE_TONES: self.available_tones}

        return None

    @property
    def available_tones(self) -> list[int | str] | None:
        """
        Return a list of available tones.

        Requires SUPPORT_TONES.
        """
        return self._attr_available_tones

"""The Color helper integration.

Each config entry produces exactly one `ColorEntity`. The entities are added
to a single shared `EntityComponent` keyed by DOMAIN so services targeting
`color.*` resolve uniformly.
"""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.service import remove_entity_service_fields
from homeassistant.helpers.typing import ConfigType, VolDictType
from homeassistant.util.hass_dict import HassKey

from .color_math import COLOR_SHAPE_FIELDS, ColorInputError
from .const import (
    DOMAIN,
    FIELD_BRIGHTNESS,
    FIELD_COLOR_NAME,
    FIELD_HEX,
    FIELD_HS,
    FIELD_KELVIN,
    FIELD_RGB,
    FIELD_XY,
    MAX_KELVIN,
    MIN_KELVIN,
    SERVICE_CLEAR_BRIGHTNESS,
    SERVICE_SET_BRIGHTNESS,
    SERVICE_SET_COLOR,
)
from .entity import ColorConfigEntry, ColorEntity

_LOGGER = logging.getLogger(__name__)

DATA_COMPONENT: HassKey[EntityComponent[ColorEntity]] = HassKey(DOMAIN)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _exactly_one_color_shape(data: dict[str, Any]) -> dict[str, Any]:
    """Ensure only one of the mutually exclusive color shapes is present."""
    present = sorted(field for field in COLOR_SHAPE_FIELDS if field in data)
    if len(present) > 1:
        raise vol.Invalid(f"Provide only one color input; got multiple: {present}")
    return data


SET_COLOR_SCHEMA = vol.All(
    cv.make_entity_service_schema(
        {
            vol.Optional(FIELD_HEX): cv.string,
            vol.Optional(FIELD_RGB): vol.All(
                cv.ensure_list,
                vol.Length(min=3, max=3),
                [vol.All(vol.Coerce(int), vol.Range(min=0, max=255))],
            ),
            vol.Optional(FIELD_HS): vol.All(
                cv.ensure_list,
                vol.Length(min=2, max=2),
                [vol.Coerce(float)],
            ),
            vol.Optional(FIELD_XY): vol.All(
                cv.ensure_list,
                vol.Length(min=2, max=2),
                [vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0))],
            ),
            vol.Optional(FIELD_KELVIN): vol.All(
                vol.Coerce(int), vol.Range(min=MIN_KELVIN, max=MAX_KELVIN)
            ),
            vol.Optional(FIELD_COLOR_NAME): cv.string,
            vol.Optional(FIELD_BRIGHTNESS): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=255)
            ),
        }
    ),
    cv.has_at_least_one_key(*COLOR_SHAPE_FIELDS),
    _exactly_one_color_shape,
)

SET_BRIGHTNESS_SCHEMA: VolDictType = {
    vol.Required(FIELD_BRIGHTNESS): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the entity component and entity services."""
    component = EntityComponent[ColorEntity](_LOGGER, DOMAIN, hass)
    hass.data[DATA_COMPONENT] = component

    async def set_color(entity: ColorEntity, call: ServiceCall) -> None:
        """Set a color from a service call."""
        color_shape = remove_entity_service_fields(call)
        try:
            await entity.async_set_color(**color_shape)
        except ColorInputError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_color_value",
                translation_placeholders={"error": str(err)},
            ) from err

    async def clear_brightness(entity: ColorEntity, call: ServiceCall) -> None:
        """Clear the stored brightness."""
        await entity.async_set_brightness(None)

    component.async_register_entity_service(
        SERVICE_SET_COLOR, SET_COLOR_SCHEMA, set_color
    )
    component.async_register_entity_service(
        SERVICE_SET_BRIGHTNESS, SET_BRIGHTNESS_SCHEMA, "async_set_brightness"
    )
    component.async_register_entity_service(
        SERVICE_CLEAR_BRIGHTNESS, {}, clear_brightness
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ColorConfigEntry) -> bool:
    """Add one entity per config entry."""
    component = hass.data[DATA_COMPONENT]
    entity = ColorEntity(entry)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await component.async_add_entities([entity])
    entry.runtime_data = entity
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ColorConfigEntry) -> bool:
    """Remove the entity when the config entry is unloaded."""
    component = hass.data[DATA_COMPONENT]
    await component.async_remove_entity(entry.runtime_data.entity_id)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ColorConfigEntry) -> None:
    """Reload the entry when options change so name/icon updates apply."""
    await hass.config_entries.async_reload(entry.entry_id)

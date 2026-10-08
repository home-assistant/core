"""Services for the light integration."""

from functools import partial
from typing import TYPE_CHECKING, Any

import probatio

from homeassistant.const import SERVICE_TOGGLE, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import VolDictType

from .const import (
    ATTR_BRIGHTNESS,
    ATTR_WHITE,
    DATA_COMPONENT,
    LIGHT_TURN_OFF_SCHEMA,
    LIGHT_TURN_ON_SCHEMA,
)
from .helper import (
    filter_turn_off_params,
    filter_turn_on_params,
    preprocess_turn_on_alternatives,
    process_turn_off_params,
    process_turn_on_params,
)

if TYPE_CHECKING:
    from . import LightEntity


def _preprocess_data(hass: HomeAssistant, data: dict[str, Any]) -> VolDictType:
    """Preprocess the service data."""
    base: VolDictType = {
        entity_field: data.pop(entity_field)  # type: ignore[arg-type]
        for entity_field in cv.ENTITY_SERVICE_FIELDS
        if entity_field in data
    }

    preprocess_turn_on_alternatives(hass, data)
    base["params"] = data
    return base


async def _async_handle_light_on_service(light: LightEntity, call: ServiceCall) -> None:
    """Handle turning a light on.

    If brightness is set to 0, this service will turn the light off.
    """
    params = process_turn_on_params(light.hass, light, call.data["params"])

    if params.get(ATTR_BRIGHTNESS) == 0 or params.get(ATTR_WHITE) == 0:
        await _async_handle_light_off_service(light, call)
    else:
        await light.async_turn_on(**filter_turn_on_params(light, params))


async def _async_handle_light_off_service(
    light: LightEntity, call: ServiceCall
) -> None:
    """Handle turning off a light."""
    params = process_turn_off_params(light.hass, light, call.data["params"])

    await light.async_turn_off(**filter_turn_off_params(light, params))


async def _async_handle_toggle_service(light: LightEntity, call: ServiceCall) -> None:
    """Handle toggling a light."""
    await light.async_toggle(**call.data["params"])


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the light services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        SERVICE_TURN_ON,
        probatio.All(
            cv.make_entity_service_schema(LIGHT_TURN_ON_SCHEMA),
            partial(_preprocess_data, hass),
        ),
        _async_handle_light_on_service,
    )

    component.async_register_entity_service(
        SERVICE_TURN_OFF,
        probatio.All(
            cv.make_entity_service_schema(LIGHT_TURN_OFF_SCHEMA),
            partial(_preprocess_data, hass),
        ),
        _async_handle_light_off_service,
    )

    component.async_register_entity_service(
        SERVICE_TOGGLE,
        probatio.All(
            cv.make_entity_service_schema(LIGHT_TURN_ON_SCHEMA),
            partial(_preprocess_data, hass),
        ),
        _async_handle_toggle_service,
    )

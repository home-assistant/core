"""Services for Nintendo Parental integration."""

from enum import StrEnum
import logging

import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import ATTR_BONUS_TIME, DOMAIN
from .coordinator import NintendoParentalControlsConfigEntry

_LOGGER = logging.getLogger(__name__)


class NintendoParentalServices(StrEnum):
    """Store keys for Nintendo Parental services."""

    ADD_BONUS_TIME = "add_bonus_time"


@callback
def async_setup_services(
    hass: HomeAssistant,
):
    """Set up the Nintendo Parental services."""
    hass.services.async_register(
        domain=DOMAIN,
        service=NintendoParentalServices.ADD_BONUS_TIME,
        service_func=async_add_bonus_time,
        schema=vol.Schema(
            {
                vol.Required(ATTR_DEVICE_ID): cv.string,
                vol.Required(ATTR_BONUS_TIME): vol.All(int, vol.Range(min=5, max=30)),
            }
        ),
    )


def _get_nintendo_device_id(dev: dr.DeviceEntry) -> str | None:
    """Get the Nintendo device ID from a device entry."""
    for identifier in dev.identifiers:
        if identifier[0] == DOMAIN:
            return identifier[1].split("_")[-1]
    return None


async def async_add_bonus_time(call: ServiceCall) -> None:
    """Add bonus time to a device."""
    config_entry: NintendoParentalControlsConfigEntry | None
    data = call.data
    device_id: str = data[ATTR_DEVICE_ID]
    bonus_time: int = data[ATTR_BONUS_TIME]
    device = dr.async_get(call.hass).async_get(device_id)
    if device is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
        )
    for entry_id in device.config_entries:
        config_entry = call.hass.config_entries.async_get_entry(entry_id)
        if config_entry is not None and config_entry.domain == DOMAIN:
            break
    nintendo_device_id = _get_nintendo_device_id(device)
    if config_entry and nintendo_device_id:
        return await config_entry.runtime_data.api.devices[
            nintendo_device_id
        ].add_extra_time(bonus_time)
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_device",
    )

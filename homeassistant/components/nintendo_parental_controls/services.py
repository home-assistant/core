"""Services for Nintendo Parental integration."""

from enum import StrEnum
import logging

import voluptuous as vol

from homeassistant.const import ATTR_CONFIG_ENTRY_ID, ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import ATTR_BONUS_TIME, DOMAIN

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
                vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
                vol.Required(ATTR_DEVICE_ID): cv.string,
                vol.Required(ATTR_BONUS_TIME): vol.All(int, vol.Range(min=5, max=30)),
            }
        ),
    )


def get_config_entry(hass: HomeAssistant, account_id: str):
    """Get the coordinator from the Home Assistant instance."""
    return hass.config_entries.async_get_entry(account_id)


async def async_add_bonus_time(call: ServiceCall) -> None:
    """Add bonus time to a device."""
    data = call.data
    config_entry = get_config_entry(call.hass, data[ATTR_CONFIG_ENTRY_ID])
    if config_entry is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_found",
        )
    device_id: str = data[ATTR_DEVICE_ID]
    bonus_time: int = data[ATTR_BONUS_TIME]
    device = dr.async_get(call.hass).async_get(device_id)
    if device is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
        )
    device_id = next(iter(device.identifiers))[1].split("_")[-1]

    coordinator = config_entry.runtime_data

    await coordinator.api.devices[device_id].add_extra_time(bonus_time)

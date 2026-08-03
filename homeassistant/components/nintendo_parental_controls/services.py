"""Services for Nintendo Parental integration."""

from enum import StrEnum
import logging

from pynintendoparental.device import Device
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID, CONF_PIN
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import ATTR_BONUS_TIME, DOMAIN
from .coordinator import NintendoParentalControlsConfigEntry

_LOGGER = logging.getLogger(__name__)


class NintendoParentalServices(StrEnum):
    """Store keys for Nintendo Parental services."""

    ADD_BONUS_TIME = "add_bonus_time"
    UPDATE_PIN_CODE = "update_pin_code"


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
    hass.services.async_register(
        domain=DOMAIN,
        service=NintendoParentalServices.UPDATE_PIN_CODE,
        service_func=async_update_pin_code,
        schema=vol.Schema(
            {
                vol.Required(ATTR_DEVICE_ID): cv.string,
                vol.Required(CONF_PIN): cv.string,
            }
        ),
    )


def _get_nintendo_device(hass: HomeAssistant, device_id: str) -> Device:
    """Get the Nintendo device from a device ID."""
    config_entry: NintendoParentalControlsConfigEntry | None
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
        )
    for entry_id in device.config_entries:
        config_entry = hass.config_entries.async_get_entry(entry_id)
        if config_entry is not None and config_entry.domain == DOMAIN:
            break
    nintendo_device_id = None
    for identifier in device.identifiers:
        if identifier[0] == DOMAIN:
            nintendo_device_id = identifier[1].split("_")[-1]
            break
    if (
        nintendo_device_id
        and config_entry
        and nintendo_device_id in config_entry.runtime_data.api.devices
    ):
        return config_entry.runtime_data.api.devices[nintendo_device_id]
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_device",
    )


async def async_add_bonus_time(call: ServiceCall) -> None:
    """Add bonus time to a device."""
    data = call.data
    device_id: str = data[ATTR_DEVICE_ID]
    bonus_time: int = data[ATTR_BONUS_TIME]
    device = _get_nintendo_device(call.hass, device_id)
    return await device.add_extra_time(bonus_time)


async def async_update_pin_code(call: ServiceCall) -> None:
    """Update the PIN code for a device."""
    data = call.data
    device_id: str = data[ATTR_DEVICE_ID]
    new_pin: str = data[CONF_PIN]
    if not new_pin.isdigit() or len(new_pin) < 4 or len(new_pin) > 8:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_pin_length",
        )
    device = _get_nintendo_device(call.hass, device_id)
    return await device.set_new_pin(new_pin)

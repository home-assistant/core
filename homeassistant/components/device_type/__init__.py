"""The device type vocabulary."""

import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.device_type import async_get_bound_device_type
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType

from .types import SmartPlug

__all__ = ["SmartPlug"]

_LOGGER = logging.getLogger(__name__)

DOMAIN = "device_type"
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the device type integration."""

    @callback
    def _async_log_missing_required_slots(hass: HomeAssistant) -> None:
        for device in dr.async_get(hass).devices:
            if (
                device.original_device_type is None
                or (bound := async_get_bound_device_type(hass, device.id)) is None
                or not (missing := bound.missing_required)
            ):
                continue
            _LOGGER.warning(
                "Device %s of type %s has no entity in its required slots %s",
                device.name_by_user or device.name or device.id,
                bound.device_type.type_id,
                ", ".join(sorted(missing)),
            )

    async_at_started(hass, _async_log_missing_required_slots)
    return True

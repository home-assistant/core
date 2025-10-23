"""Services for LG ThinQ integration."""

from __future__ import annotations

from datetime import date
import logging
from typing import TYPE_CHECKING, Final

from thinqconnect import USAGE_DAILY, USAGE_MONTHLY, ThinQAPIException
from thinqconnect.integration import ThinQPropertyEx
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

if TYPE_CHECKING:
    from . import ThinqConfigEntry
from .const import DOMAIN
from .coordinator import DeviceDataUpdateCoordinator

ATTR_PERIOD: Final = "period"
ATTR_START: Final = "start_date"
ATTR_END: Final = "end_date"

ENERGY_SERVICE_NAME: Final = "service_get_energy_usage"

ENERGY_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_PERIOD): cv.string,
        vol.Required(ATTR_START): cv.date,
        vol.Required(ATTR_END): cv.date,
    }
)
WASHER_SUB_IDS = ["washerDryer", "dryer", "washer"]
_LOGGER = logging.getLogger(__name__)


def __get_coordinator(call: ServiceCall) -> DeviceDataUpdateCoordinator | None:
    """Get the coordinator by device_id."""
    device_id = call.data[ATTR_DEVICE_ID]
    device_registry = dr.async_get(call.hass)

    if (device_entry := device_registry.async_get(device_id)) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_device_id",
        )
    config_entries = list[ConfigEntry]()

    for entry_id in device_entry.config_entries:
        if (entry := call.hass.config_entries.async_get_entry(entry_id)) is None:
            continue
        if entry.domain == DOMAIN and entry.state == ConfigEntryState.LOADED:
            config_entries.append(entry)

    if not config_entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_config_entry",
        )

    unique_id = next(iter(device_entry.identifiers))[1]
    for config_entry in config_entries:
        if (
            coordinator := config_entry.runtime_data.coordinators.get(unique_id)
        ) is not None:
            return coordinator
    return None


async def __get_energy_usage(call: ServiceCall) -> ServiceResponse:
    """Get energy usage."""
    service_data = call.data
    period = service_data[ATTR_PERIOD]
    start_date: date = service_data[ATTR_START]
    end_date: date = service_data[ATTR_END]

    if end_date < start_date:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="end_date_before_start_date",
        )
    if not (coordinator := __get_coordinator(call)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_device_id",
        )
    _LOGGER.debug(
        "[%s] __get_energy_usage data: %s",
        coordinator.device_name,
        service_data,
    )
    energy_property = ThinQPropertyEx.ENERGY_USAGE
    for sub in WASHER_SUB_IDS:
        if sub in coordinator.unique_id:
            energy_property = f"{ThinQPropertyEx.ENERGY_USAGE}_{sub}"
            break
    try:
        result = await coordinator.api.async_get_energy_usage(
            energy_property=energy_property,
            period=USAGE_MONTHLY if period == "monthly" else USAGE_DAILY,
            start_date=start_date,
            end_date=end_date,
            detail=True,
        )
        _LOGGER.warning(
            "[%s] __get_energy_usage energy_property: %s, result: %s",
            coordinator.device_name,
            energy_property,
            result,
        )
        if result:
            result_value: float = 0.0
            for data in result:
                result_value += data.get(energy_property, 0)
            return {"total": int(result_value), "energy_usage": result}

    except ThinQAPIException as exc:
        _LOGGER.warning(
            "[%s] Failed get energy usage: %s", coordinator.device_name, exc
        )
        raise ServiceValidationError(exc, translation_domain=DOMAIN) from exc
    return {}


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for LG ThinQ integration."""
    hass.services.async_register(
        DOMAIN,
        ENERGY_SERVICE_NAME,
        __get_energy_usage,
        schema=ENERGY_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


async def async_unload_services(hass: HomeAssistant, entry: ThinqConfigEntry) -> None:
    """Unload services."""
    if hass.data.get(DOMAIN):
        return

    hass.services.async_remove(domain=DOMAIN, service=ENERGY_SERVICE_NAME)

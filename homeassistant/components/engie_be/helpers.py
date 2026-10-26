"""Shared helpers for the ENGIE Belgium automation triggers and conditions."""

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

import probatio

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, CONF_ABOVE, CONF_BELOW, CONF_OPTIONS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import EngieBeEpexCoordinator, EngieBeEpexData

if TYPE_CHECKING:
    from . import EngieBeRuntimeData

DEVICE_IDS_SCHEMA: dict[probatio.Marker, Any] = {
    probatio.Required(ATTR_DEVICE_ID): probatio.All(
        probatio.EnsureList(), probatio.Length(min=1), [cv.string]
    ),
}


def _validate_threshold(options: dict[str, Any]) -> dict[str, Any]:
    """Require at least one bound and a range that is not empty."""
    above = options.get(CONF_ABOVE)
    below = options.get(CONF_BELOW)
    if above is None and below is None:
        raise probatio.Invalid("Set above, below or both")
    if above is not None and below is not None and above >= below:
        raise probatio.Invalid("Above must be lower than below")
    return options


DEVICE_IDS_OPTIONS_SCHEMA = probatio.Schema(DEVICE_IDS_SCHEMA)

THRESHOLD_OPTIONS_SCHEMA = probatio.Schema(
    probatio.All(
        {
            **DEVICE_IDS_SCHEMA,
            probatio.Optional(CONF_ABOVE): probatio.Coerce(float),
            probatio.Optional(CONF_BELOW): probatio.Coerce(float),
        },
        _validate_threshold,
    )
)


def price_in_range(price: float, above: float | None, below: float | None) -> bool:
    """Return True when the price is above the lower and below the upper bound."""
    return (above is None or price > above) and (below is None or price < below)


@callback
def async_validate_device_ids(hass: HomeAssistant, device_ids: Iterable[str]) -> None:
    """Raise when a device does not belong to ENGIE Belgium."""
    for device_id in device_ids:
        _, entry = dr.async_get_device_and_config_entry_for_domain(
            hass, device_id, domain=DOMAIN
        )
        if entry is None:
            raise probatio.Invalid(f"Device {device_id} is not an ENGIE Belgium device")


@callback
def async_validate_epex_options(
    hass: HomeAssistant, config: ConfigType, options_schema: probatio.Schema
) -> ConfigType:
    """Validate the options and check that every device belongs to ENGIE Belgium."""
    config = probatio.Schema({probatio.Required(CONF_OPTIONS): options_schema})(config)
    async_validate_device_ids(hass, config[CONF_OPTIONS][ATTR_DEVICE_ID])
    return config


@callback
def async_get_device_epex(
    hass: HomeAssistant, device_id: str
) -> EngieBeEpexCoordinator | None:
    """Return the EPEX coordinator when the device has a dynamic tariff."""
    device, entry = dr.async_get_device_and_config_entry_for_domain(
        hass, device_id, domain=DOMAIN
    )
    if device is None or entry is None or entry.state is not ConfigEntryState.LOADED:
        return None
    runtime_data: EngieBeRuntimeData = entry.runtime_data
    if runtime_data.epex is None:
        return None
    if not any(
        (household := runtime_data.households.get(ban)) is not None
        and household.is_dynamic
        for domain, ban in device.identifiers
        if domain == DOMAIN
    ):
        return None
    return runtime_data.epex


@callback
def async_get_device_epex_data(
    hass: HomeAssistant, device_id: str
) -> EngieBeEpexData | None:
    """Return the EPEX prices of the device when the last fetch succeeded."""
    epex = async_get_device_epex(hass, device_id)
    if epex is None or not epex.last_update_success:
        return None
    return epex.data

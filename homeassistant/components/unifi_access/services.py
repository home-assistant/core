"""Services for UniFi Access."""

from datetime import timedelta
from enum import StrEnum

import probatio
from unifi_access_api import UnifiAccessError

from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN, MAX_LOCK_RULE_INTERVAL, MIN_LOCK_RULE_INTERVAL
from .coordinator import UnifiAccessConfigEntry


class UnifiAccessService(StrEnum):
    """Store keys for UniFi Access services."""

    SET_LOCK_RULE = "set_lock_rule"


class UnifiAccessServiceArgument(StrEnum):
    """Store keys for UniFi Access service arguments."""

    INTERVAL = "interval"
    RULE = "rule"


LOCK_RULE_OPTIONS = [
    "keep_lock",
    "keep_unlock",
    "custom",
    "reset",
    "lock_early",
]

SERVICE_SET_LOCK_RULE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
        probatio.Required(UnifiAccessServiceArgument.RULE): probatio.In(
            LOCK_RULE_OPTIONS
        ),
        probatio.Optional(UnifiAccessServiceArgument.INTERVAL): probatio.All(
            cv.time_period,
            cv.positive_timedelta,
            probatio.Range(
                min=timedelta(minutes=MIN_LOCK_RULE_INTERVAL),
                max=timedelta(minutes=MAX_LOCK_RULE_INTERVAL),
            ),
        ),
    }
)


@callback
def _async_get_target(
    hass: HomeAssistant, call: ServiceCall
) -> tuple[UnifiAccessConfigEntry, str]:
    """Resolve a service call to a UniFi Access config entry and door ID."""
    config_entry: UnifiAccessConfigEntry
    device, config_entry = service.async_get_device_and_config_entry(
        hass, DOMAIN, call.data[CommonServiceArgument.DEVICE_ID]
    )
    coordinator = config_entry.runtime_data
    for identifier_domain, identifier_value in device.identifiers:
        if identifier_domain == DOMAIN and identifier_value in coordinator.data.doors:
            return config_entry, identifier_value

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_target",
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the UniFi Access integration."""

    async def _handle_set_lock_rule(call: ServiceCall) -> None:
        """Set a temporary lock rule for a UniFi Access door."""
        config_entry, door_id = _async_get_target(hass, call)
        interval: timedelta | None = call.data.get(UnifiAccessServiceArgument.INTERVAL)
        interval_minutes = (
            interval.total_seconds() / 60 if interval is not None else None
        )
        try:
            await config_entry.runtime_data.async_set_lock_rule(
                door_id, call.data[UnifiAccessServiceArgument.RULE], interval_minutes
            )
        except UnifiAccessError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="lock_rule_failed",
            ) from err

    hass.services.async_register(
        DOMAIN,
        UnifiAccessService.SET_LOCK_RULE,
        _handle_set_lock_rule,
        schema=SERVICE_SET_LOCK_RULE_SCHEMA,
    )

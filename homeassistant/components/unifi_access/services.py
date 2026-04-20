"""Services for UniFi Access."""

from __future__ import annotations

from datetime import timedelta

from unifi_access_api import UnifiAccessError
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    service,
)

from .const import (
    ATTR_INTERVAL,
    ATTR_RULE,
    DOMAIN,
    MAX_LOCK_RULE_INTERVAL,
    MIN_LOCK_RULE_INTERVAL,
    SERVICE_SET_LOCK_RULE,
)
from .coordinator import UnifiAccessConfigEntry

LOCK_RULE_OPTIONS = [
    "keep_lock",
    "keep_unlock",
    "custom",
    "reset",
    "lock_early",
]

SERVICE_SET_LOCK_RULE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_RULE): vol.In(LOCK_RULE_OPTIONS),
        vol.Optional(ATTR_INTERVAL): vol.All(
            cv.time_period,
            cv.positive_timedelta,
            vol.Range(
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
    device_registry = dr.async_get(hass)
    device_id = call.data[ATTR_DEVICE_ID]
    if (device := device_registry.async_get(device_id)) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_target",
        )

    for entry_id in device.config_entries:
        if (
            entry := hass.config_entries.async_get_entry(entry_id)
        ) is None or entry.domain != DOMAIN:
            continue

        config_entry: UnifiAccessConfigEntry = service.async_get_config_entry(
            hass, DOMAIN, entry_id
        )
        coordinator = config_entry.runtime_data
        for identifier_domain, identifier_value in device.identifiers:
            if (
                identifier_domain == DOMAIN
                and identifier_value in coordinator.data.doors
            ):
                return config_entry, identifier_value

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_target",
    )


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the UniFi Access integration."""

    async def _handle_set_lock_rule(call: ServiceCall) -> None:
        """Set a temporary lock rule for a UniFi Access door."""
        config_entry, door_id = _async_get_target(hass, call)
        interval: timedelta | None = call.data.get(ATTR_INTERVAL)
        interval_minutes = (
            interval.total_seconds() / 60 if interval is not None else None
        )
        try:
            await config_entry.runtime_data.async_set_lock_rule(
                door_id, call.data[ATTR_RULE], interval_minutes
            )
        except UnifiAccessError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="lock_rule_failed",
            ) from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_LOCK_RULE,
        _handle_set_lock_rule,
        schema=SERVICE_SET_LOCK_RULE_SCHEMA,
    )

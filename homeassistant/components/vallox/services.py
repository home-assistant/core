"""Services for the Vallox integration."""

from __future__ import annotations

from collections.abc import Iterator
import logging

from vallox_websocket_api import Profile, Vallox, ValloxApiException
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback

from .const import DOMAIN, I18N_KEY_TO_VALLOX_PROFILE
from .coordinator import ValloxDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

ATTR_PROFILE_FAN_SPEED = "fan_speed"
ATTR_PROFILE = "profile"
ATTR_DURATION = "duration"

SERVICE_SET_PROFILE_FAN_SPEED_HOME = "set_profile_fan_speed_home"
SERVICE_SET_PROFILE_FAN_SPEED_AWAY = "set_profile_fan_speed_away"
SERVICE_SET_PROFILE_FAN_SPEED_BOOST = "set_profile_fan_speed_boost"
SERVICE_SET_PROFILE = "set_profile"

SERVICE_SCHEMA_SET_PROFILE_FAN_SPEED = vol.Schema(
    {
        vol.Required(ATTR_PROFILE_FAN_SPEED): vol.All(
            vol.Coerce(int), vol.Clamp(min=0, max=100)
        )
    }
)

SERVICE_SCHEMA_SET_PROFILE = vol.Schema(
    {
        vol.Required(ATTR_PROFILE): vol.In(I18N_KEY_TO_VALLOX_PROFILE),
        vol.Optional(ATTR_DURATION): vol.All(
            vol.Coerce(int), vol.Clamp(min=1, max=65535)
        ),
    }
)

SERVICE_TO_PROFILE = {
    SERVICE_SET_PROFILE_FAN_SPEED_HOME: Profile.HOME,
    SERVICE_SET_PROFILE_FAN_SPEED_AWAY: Profile.AWAY,
    SERVICE_SET_PROFILE_FAN_SPEED_BOOST: Profile.BOOST,
}


def _iter_loaded_clients(
    hass: HomeAssistant,
) -> Iterator[tuple[Vallox, ValloxDataUpdateCoordinator]]:
    """Yield (client, coordinator) for every loaded Vallox config entry."""
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        data = hass.data[DOMAIN][entry.entry_id]
        yield data["client"], data["coordinator"]


async def _async_set_profile_fan_speed(call: ServiceCall) -> None:
    """Set the fan speed in percent for the profile matching the called service."""
    profile = SERVICE_TO_PROFILE[call.service]
    fan_speed: int = call.data[ATTR_PROFILE_FAN_SPEED]
    _LOGGER.debug("Setting %s fan speed to: %d%%", profile.name, fan_speed)

    for client, coordinator in _iter_loaded_clients(call.hass):
        try:
            await client.set_fan_speed(profile, fan_speed)
        except ValloxApiException as err:
            _LOGGER.error(
                "Error setting fan speed for %s profile: %s", profile.name, err
            )
            continue
        await coordinator.async_request_refresh()


async def _async_set_profile(call: ServiceCall) -> None:
    """Activate the given profile for the given duration."""
    profile_key: str = call.data[ATTR_PROFILE]
    duration: int | None = call.data.get(ATTR_DURATION)
    _LOGGER.debug("Activating profile %s for %s min", profile_key, duration)

    for client, coordinator in _iter_loaded_clients(call.hass):
        try:
            await client.set_profile(I18N_KEY_TO_VALLOX_PROFILE[profile_key], duration)
        except ValloxApiException as err:
            _LOGGER.error(
                "Error setting profile %s for duration %s: %s",
                profile_key,
                duration,
                err,
            )
            continue
        await coordinator.async_request_refresh()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Vallox services."""
    for service_name in SERVICE_TO_PROFILE:
        hass.services.async_register(
            DOMAIN,
            service_name,
            _async_set_profile_fan_speed,
            schema=SERVICE_SCHEMA_SET_PROFILE_FAN_SPEED,
        )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PROFILE,
        _async_set_profile,
        schema=SERVICE_SCHEMA_SET_PROFILE,
    )

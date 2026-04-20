"""Services for the Vallox integration."""

from __future__ import annotations

from enum import StrEnum, auto
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


class ValloxService(StrEnum):
    """Vallox service names."""

    SET_PROFILE_FAN_SPEED_HOME = auto()
    SET_PROFILE_FAN_SPEED_AWAY = auto()
    SET_PROFILE_FAN_SPEED_BOOST = auto()
    SET_PROFILE = auto()


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


def _get_client(
    hass: HomeAssistant,
) -> tuple[Vallox, ValloxDataUpdateCoordinator]:
    """Return (client, coordinator) for Vallox config entry."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if len(entries) != 1:
        raise ValueError("Expected exactly one loaded Vallox config entry")

    data = hass.data[DOMAIN][entries[0].entry_id]
    return data["client"], data["coordinator"]


async def _async_set_profile_fan_speed(call: ServiceCall, profile: Profile) -> None:
    """Set the fan speed in percent for the profile matching the called service."""
    fan_speed: int = call.data[ATTR_PROFILE_FAN_SPEED]
    _LOGGER.debug("Setting %s fan speed to: %d%%", profile.name, fan_speed)

    client, coordinator = _get_client(call.hass)
    try:
        await client.set_fan_speed(profile, fan_speed)
    except ValloxApiException as err:
        _LOGGER.error("Error setting fan speed for %s profile: %s", profile.name, err)
    else:
        await coordinator.async_request_refresh()


async def _async_set_profile_fan_speed_away(call: ServiceCall) -> None:
    """Set the fan speed in percent for the Away profile."""
    await _async_set_profile_fan_speed(call, Profile.AWAY)


async def _async_set_profile_fan_speed_boost(call: ServiceCall) -> None:
    """Set the fan speed in percent for the Boost profile."""
    await _async_set_profile_fan_speed(call, Profile.BOOST)


async def _async_set_profile_fan_speed_home(call: ServiceCall) -> None:
    """Set the fan speed in percent for the Home profile."""
    await _async_set_profile_fan_speed(call, Profile.HOME)


async def _async_set_profile(call: ServiceCall) -> None:
    """Activate the given profile for the given duration."""
    profile_key: str = call.data[ATTR_PROFILE]
    duration: int | None = call.data.get(ATTR_DURATION)
    _LOGGER.debug("Activating profile %s for %s min", profile_key, duration)

    client, coordinator = _get_client(call.hass)
    try:
        await client.set_profile(I18N_KEY_TO_VALLOX_PROFILE[profile_key], duration)
    except ValloxApiException as err:
        _LOGGER.error(
            "Error setting profile %s for duration %s: %s",
            profile_key,
            duration,
            err,
        )
    else:
        await coordinator.async_request_refresh()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Vallox services."""
    hass.services.async_register(
        DOMAIN,
        ValloxService.SET_PROFILE_FAN_SPEED_AWAY,
        _async_set_profile_fan_speed_away,
        schema=SERVICE_SCHEMA_SET_PROFILE_FAN_SPEED,
    )
    hass.services.async_register(
        DOMAIN,
        ValloxService.SET_PROFILE_FAN_SPEED_BOOST,
        _async_set_profile_fan_speed_boost,
        schema=SERVICE_SCHEMA_SET_PROFILE_FAN_SPEED,
    )
    hass.services.async_register(
        DOMAIN,
        ValloxService.SET_PROFILE_FAN_SPEED_HOME,
        _async_set_profile_fan_speed_home,
        schema=SERVICE_SCHEMA_SET_PROFILE_FAN_SPEED,
    )
    hass.services.async_register(
        DOMAIN,
        ValloxService.SET_PROFILE,
        _async_set_profile,
        schema=SERVICE_SCHEMA_SET_PROFILE,
    )

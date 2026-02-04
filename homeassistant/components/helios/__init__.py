"""Support for Helios Ventilation units."""

from __future__ import annotations

import ipaddress
import logging

from helios_websocket_api import Profile, Helios, HeliosApiException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_NAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    DEFAULT_FAN_SPEED_AWAY,
    DEFAULT_FAN_SPEED_BOOST,
    DEFAULT_FAN_SPEED_HOME,
    DEFAULT_NAME,
    DOMAIN,
    I18N_KEY_TO_HELIOS_PROFILE,
)
from .coordinator import HeliosDataUpdateCoordinator

type HeliosConfigEntry = ConfigEntry[HeliosDataUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_HOST): vol.All(ipaddress.ip_address, cv.string),
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS: list[Platform] = [Platform.FAN, Platform.NUMBER, Platform.SENSOR, Platform.SWITCH]

ATTR_PROFILE_FAN_SPEED = "fan_speed"

SERVICE_SCHEMA_SET_PROFILE_FAN_SPEED = vol.Schema(
    {
        vol.Required(ATTR_PROFILE_FAN_SPEED): vol.All(
            vol.Coerce(int), vol.Clamp(min=0, max=100)
        )
    }
)

ATTR_PROFILE = "profile"
ATTR_DURATION = "duration"

SERVICE_SCHEMA_SET_PROFILE = vol.Schema(
    {
        vol.Required(ATTR_PROFILE): vol.In(I18N_KEY_TO_HELIOS_PROFILE),
        vol.Optional(ATTR_DURATION): vol.All(
            vol.Coerce(int), vol.Clamp(min=1, max=65535)
        ),
    }
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Helios integration."""

    async def async_set_profile_fan_speed(
        call: ServiceCall, profile: Profile
    ) -> None:
        """Set the fan speed for a specific profile."""
        fan_speed = call.data[ATTR_PROFILE_FAN_SPEED]

        # Get the first loaded config entry (single-platform integration)
        entries = hass.config_entries.async_loaded_entries(DOMAIN)
        if not entries:
            raise ServiceValidationError("No Helios device configured")

        entry: HeliosConfigEntry = entries[0]
        coordinator = entry.runtime_data
        client = coordinator.client

        _LOGGER.debug("Setting %s fan speed to: %d%%", profile.name, fan_speed)

        try:
            await client.set_fan_speed(profile, fan_speed)
        except HeliosApiException as err:
            raise HomeAssistantError(
                f"Failed to set fan speed for {profile.name} profile"
            ) from err

        await coordinator.async_request_refresh()

    async def async_set_profile_fan_speed_home(call: ServiceCall) -> None:
        """Set the fan speed for the Home profile."""
        await async_set_profile_fan_speed(call, Profile.HOME)

    async def async_set_profile_fan_speed_away(call: ServiceCall) -> None:
        """Set the fan speed for the Away profile."""
        await async_set_profile_fan_speed(call, Profile.AWAY)

    async def async_set_profile_fan_speed_boost(call: ServiceCall) -> None:
        """Set the fan speed for the Boost profile."""
        await async_set_profile_fan_speed(call, Profile.BOOST)

    async def async_set_profile(call: ServiceCall) -> None:
        """Activate a profile with optional duration."""
        profile = call.data[ATTR_PROFILE]
        duration = call.data.get(ATTR_DURATION)

        # Get the first loaded config entry (single-platform integration)
        entries = hass.config_entries.async_loaded_entries(DOMAIN)
        if not entries:
            raise ServiceValidationError("No Helios device configured")

        entry: HeliosConfigEntry = entries[0]
        coordinator = entry.runtime_data
        client = coordinator.client

        _LOGGER.debug("Activating profile %s for %s min", profile, duration)

        try:
            await client.set_profile(I18N_KEY_TO_HELIOS_PROFILE[profile], duration)
        except HeliosApiException as err:
            raise HomeAssistantError(
                f"Failed to set profile {profile}"
            ) from err

        await coordinator.async_request_refresh()

    # Register services
    hass.services.async_register(
        DOMAIN,
        "set_profile_fan_speed_home",
        async_set_profile_fan_speed_home,
        schema=SERVICE_SCHEMA_SET_PROFILE_FAN_SPEED,
    )

    hass.services.async_register(
        DOMAIN,
        "set_profile_fan_speed_away",
        async_set_profile_fan_speed_away,
        schema=SERVICE_SCHEMA_SET_PROFILE_FAN_SPEED,
    )

    hass.services.async_register(
        DOMAIN,
        "set_profile_fan_speed_boost",
        async_set_profile_fan_speed_boost,
        schema=SERVICE_SCHEMA_SET_PROFILE_FAN_SPEED,
    )

    hass.services.async_register(
        DOMAIN,
        "set_profile",
        async_set_profile,
        schema=SERVICE_SCHEMA_SET_PROFILE,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: HeliosConfigEntry) -> bool:
    """Set up Helios from a config entry."""
    host = entry.data[CONF_HOST]

    client = Helios(host)
    coordinator = HeliosDataUpdateCoordinator(hass, entry, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HeliosConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

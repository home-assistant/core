"""Support for Vallox ventilation units."""

from __future__ import annotations

import ipaddress
import logging
from typing import NamedTuple

from vallox_websocket_api import Profile, Vallox, ValloxApiException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    DEFAULT_FAN_SPEED_AWAY,
    DEFAULT_FAN_SPEED_BOOST,
    DEFAULT_FAN_SPEED_HOME,
    DEFAULT_NAME,
    DOMAIN,
    I18N_KEY_TO_VALLOX_PROFILE,
)
from .coordinator import ValloxDataUpdateCoordinator

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

PLATFORMS: list[str] = [
    Platform.BINARY_SENSOR,
    Platform.DATE,
    Platform.FAN,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

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
        vol.Required(ATTR_PROFILE): vol.In(I18N_KEY_TO_VALLOX_PROFILE),
        vol.Optional(ATTR_DURATION): vol.All(
            vol.Coerce(int), vol.Clamp(min=1, max=65535)
        ),
    }
)


class ServiceMethodDetails(NamedTuple):
    """Details for SERVICE_TO_METHOD mapping."""

    method: str
    schema: vol.Schema


SERVICE_SET_PROFILE_FAN_SPEED_HOME = "set_profile_fan_speed_home"
SERVICE_SET_PROFILE_FAN_SPEED_AWAY = "set_profile_fan_speed_away"
SERVICE_SET_PROFILE_FAN_SPEED_BOOST = "set_profile_fan_speed_boost"
SERVICE_SET_PROFILE = "set_profile"

SERVICE_TO_METHOD = {
    SERVICE_SET_PROFILE_FAN_SPEED_HOME: ServiceMethodDetails(
        method="async_set_profile_fan_speed_home",
        schema=SERVICE_SCHEMA_SET_PROFILE_FAN_SPEED,
    ),
    SERVICE_SET_PROFILE_FAN_SPEED_AWAY: ServiceMethodDetails(
        method="async_set_profile_fan_speed_away",
        schema=SERVICE_SCHEMA_SET_PROFILE_FAN_SPEED,
    ),
    SERVICE_SET_PROFILE_FAN_SPEED_BOOST: ServiceMethodDetails(
        method="async_set_profile_fan_speed_boost",
        schema=SERVICE_SCHEMA_SET_PROFILE_FAN_SPEED,
    ),
    SERVICE_SET_PROFILE: ServiceMethodDetails(
        method="async_set_profile", schema=SERVICE_SCHEMA_SET_PROFILE
    ),
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the client and boot the platforms."""
    host = entry.data[CONF_HOST]
    name = entry.data[CONF_NAME]

    client = Vallox(host)

    coordinator = ValloxDataUpdateCoordinator(hass, name, client)

    await coordinator.async_config_entry_first_refresh()

    service_handler = ValloxServiceHandler(client, coordinator)
    for vallox_service, service_details in SERVICE_TO_METHOD.items():
        hass.services.async_register(
            DOMAIN,
            vallox_service,
            service_handler.async_handle,
            schema=service_details.schema,
        )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "name": name,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

        if hass.data[DOMAIN]:
            return unload_ok

        for service in SERVICE_TO_METHOD:
            hass.services.async_remove(DOMAIN, service)

    return unload_ok


class ValloxServiceHandler:
    """Services implementation."""

    def __init__(
        self, client: Vallox, coordinator: ValloxDataUpdateCoordinator
    ) -> None:
        """Initialize the proxy."""
        self._client = client
        self._coordinator = coordinator

    async def async_set_profile_fan_speed_home(
        self, fan_speed: int = DEFAULT_FAN_SPEED_HOME
    ) -> bool:
        """Set the fan speed in percent for the Home profile."""
        _LOGGER.debug("Setting Home fan speed to: %d%%", fan_speed)

        try:
            await self._client.set_fan_speed(Profile.HOME, fan_speed)
        except ValloxApiException as err:
            _LOGGER.error("Error setting fan speed for Home profile: %s", err)
            return False
        return True

    async def async_set_profile_fan_speed_away(
        self, fan_speed: int = DEFAULT_FAN_SPEED_AWAY
    ) -> bool:
        """Set the fan speed in percent for the Away profile."""
        _LOGGER.debug("Setting Away fan speed to: %d%%", fan_speed)

        try:
            await self._client.set_fan_speed(Profile.AWAY, fan_speed)
        except ValloxApiException as err:
            _LOGGER.error("Error setting fan speed for Away profile: %s", err)
            return False
        return True

    async def async_set_profile_fan_speed_boost(
        self, fan_speed: int = DEFAULT_FAN_SPEED_BOOST
    ) -> bool:
        """Set the fan speed in percent for the Boost profile."""
        _LOGGER.debug("Setting Boost fan speed to: %d%%", fan_speed)

        try:
            await self._client.set_fan_speed(Profile.BOOST, fan_speed)
        except ValloxApiException as err:
            _LOGGER.error("Error setting fan speed for Boost profile: %s", err)
            return False
        return True

    async def async_set_profile(
        self, profile: str, duration: int | None = None
    ) -> bool:
        """Activate profile for given duration."""
        _LOGGER.debug("Activating profile %s for %s min", profile, duration)
        try:
            await self._client.set_profile(
                I18N_KEY_TO_VALLOX_PROFILE[profile], duration
            )
        except ValloxApiException as err:
            _LOGGER.error(
                "Error setting profile %d for duration %s: %s", profile, duration, err
            )
            return False
        return True

    async def async_handle(self, call: ServiceCall) -> None:
        """Dispatch a service call."""
        service_details = SERVICE_TO_METHOD.get(call.service)
        params = call.data.copy()

        if service_details is None:
            return

        if not hasattr(self, service_details.method):
            _LOGGER.error("Service not implemented: %s", service_details.method)
            return

        result = await getattr(self, service_details.method)(**params)

        # This state change affects other entities like sensors. Force an immediate update that can
        # be observed by all parties involved.
        if result:
            await self._coordinator.async_request_refresh()

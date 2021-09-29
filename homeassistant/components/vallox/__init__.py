"""Support for Vallox ventilation units."""
from __future__ import annotations

from datetime import datetime
import ipaddress
import logging
from typing import Any

from vallox_websocket_api import PROFILE as VALLOX_PROFILE, Vallox
from vallox_websocket_api.constants import vlxDevConstants
from vallox_websocket_api.exceptions import ValloxApiException
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, StateType

from .const import (
    DEFAULT_FAN_SPEED_AWAY,
    DEFAULT_FAN_SPEED_BOOST,
    DEFAULT_FAN_SPEED_HOME,
    DEFAULT_NAME,
    DOMAIN,
    METRIC_KEY_PROFILE_FAN_SPEED_AWAY,
    METRIC_KEY_PROFILE_FAN_SPEED_BOOST,
    METRIC_KEY_PROFILE_FAN_SPEED_HOME,
    SIGNAL_VALLOX_STATE_UPDATE,
    STATE_PROXY_SCAN_INTERVAL,
    STR_TO_VALLOX_PROFILE_SETTABLE,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): vol.All(ipaddress.ip_address, cv.string),
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

ATTR_PROFILE = "profile"
ATTR_PROFILE_FAN_SPEED = "fan_speed"

SERVICE_SCHEMA_SET_PROFILE = vol.Schema(
    {
        vol.Required(ATTR_PROFILE): vol.All(
            cv.string, vol.In(STR_TO_VALLOX_PROFILE_SETTABLE)
        )
    }
)

SERVICE_SCHEMA_SET_PROFILE_FAN_SPEED = vol.Schema(
    {
        vol.Required(ATTR_PROFILE_FAN_SPEED): vol.All(
            vol.Coerce(int), vol.Clamp(min=0, max=100)
        )
    }
)

SERVICE_SET_PROFILE = "set_profile"
SERVICE_SET_PROFILE_FAN_SPEED_HOME = "set_profile_fan_speed_home"
SERVICE_SET_PROFILE_FAN_SPEED_AWAY = "set_profile_fan_speed_away"
SERVICE_SET_PROFILE_FAN_SPEED_BOOST = "set_profile_fan_speed_boost"

SERVICE_TO_METHOD = {
    SERVICE_SET_PROFILE: {
        "method": "async_set_profile",
        "schema": SERVICE_SCHEMA_SET_PROFILE,
    },
    SERVICE_SET_PROFILE_FAN_SPEED_HOME: {
        "method": "async_set_profile_fan_speed_home",
        "schema": SERVICE_SCHEMA_SET_PROFILE_FAN_SPEED,
    },
    SERVICE_SET_PROFILE_FAN_SPEED_AWAY: {
        "method": "async_set_profile_fan_speed_away",
        "schema": SERVICE_SCHEMA_SET_PROFILE_FAN_SPEED,
    },
    SERVICE_SET_PROFILE_FAN_SPEED_BOOST: {
        "method": "async_set_profile_fan_speed_boost",
        "schema": SERVICE_SCHEMA_SET_PROFILE_FAN_SPEED,
    },
}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the client and boot the platforms."""
    conf = config[DOMAIN]
    host = conf.get(CONF_HOST)
    name = conf.get(CONF_NAME)

    client = Vallox(host)
    state_proxy = ValloxStateProxy(hass, client)
    service_handler = ValloxServiceHandler(client, state_proxy)

    hass.data[DOMAIN] = {"client": client, "state_proxy": state_proxy, "name": name}

    for vallox_service, method in SERVICE_TO_METHOD.items():
        schema = method["schema"]
        hass.services.async_register(
            DOMAIN, vallox_service, service_handler.async_handle, schema=schema
        )

    # The vallox hardware expects quite strict timings for websocket requests. Timings that machines
    # with less processing power, like Raspberries, cannot live up to during the busy start phase of
    # Home Asssistant. Hence, async_add_entities() for fan and sensor in respective code will be
    # called with update_before_add=False to intentionally delay the first request, increasing
    # chance that it is issued only when the machine is less busy again.
    hass.async_create_task(async_load_platform(hass, "sensor", DOMAIN, {}, config))
    hass.async_create_task(async_load_platform(hass, "fan", DOMAIN, {}, config))

    async_track_time_interval(hass, state_proxy.async_update, STATE_PROXY_SCAN_INTERVAL)

    return True


class ValloxStateProxy:
    """Helper class to reduce websocket API calls."""

    def __init__(self, hass: HomeAssistant, client: Vallox) -> None:
        """Initialize the proxy."""
        self._hass = hass
        self._client = client
        self._metric_cache: dict[str, Any] = {}
        self._profile = VALLOX_PROFILE.NONE
        self._valid = False

    def fetch_metric(self, metric_key: str) -> StateType:
        """Return cached state value."""
        _LOGGER.debug("Fetching metric key: %s", metric_key)

        if not self._valid:
            raise OSError("Device state out of sync.")

        if metric_key not in vlxDevConstants.__dict__:
            raise KeyError(f"Unknown metric key: {metric_key}")

        value = self._metric_cache[metric_key]
        if value is None:
            return None

        if not isinstance(value, (str, int, float)):
            raise TypeError(
                f"Return value of metric {metric_key} has unexpected type {type(value)}"
            )

        return value

    def get_profile(self) -> VALLOX_PROFILE:
        """Return cached profile value."""
        _LOGGER.debug("Returning profile")

        if not self._valid:
            raise OSError("Device state out of sync.")

        return self._profile

    async def async_update(self, time: datetime | None = None) -> None:
        """Fetch state update."""
        _LOGGER.debug("Updating Vallox state cache")

        try:
            self._metric_cache = await self._client.fetch_metrics()
            self._profile = await self._client.get_profile()

        except (OSError, ValloxApiException) as err:
            self._valid = False
            _LOGGER.error("Error during state cache update: %s", err)
            return

        self._valid = True
        async_dispatcher_send(self._hass, SIGNAL_VALLOX_STATE_UPDATE)


class ValloxServiceHandler:
    """Services implementation."""

    def __init__(self, client: Vallox, state_proxy: ValloxStateProxy) -> None:
        """Initialize the proxy."""
        self._client = client
        self._state_proxy = state_proxy

    async def async_set_profile(self, profile: str = "Home") -> bool:
        """Set the ventilation profile."""
        _LOGGER.debug("Setting ventilation profile to: %s", profile)

        _LOGGER.warning(
            "Attention: The service 'vallox.set_profile' is superseded by the 'fan.set_preset_mode' service."
            "It will be removed in the future, please migrate to 'fan.set_preset_mode' to prevent breakage"
        )

        try:
            await self._client.set_profile(STR_TO_VALLOX_PROFILE_SETTABLE[profile])
            return True

        except (OSError, ValloxApiException) as err:
            _LOGGER.error("Error setting ventilation profile: %s", err)
            return False

    async def async_set_profile_fan_speed_home(
        self, fan_speed: int = DEFAULT_FAN_SPEED_HOME
    ) -> bool:
        """Set the fan speed in percent for the Home profile."""
        _LOGGER.debug("Setting Home fan speed to: %d%%", fan_speed)

        try:
            await self._client.set_values(
                {METRIC_KEY_PROFILE_FAN_SPEED_HOME: fan_speed}
            )
            return True

        except (OSError, ValloxApiException) as err:
            _LOGGER.error("Error setting fan speed for Home profile: %s", err)
            return False

    async def async_set_profile_fan_speed_away(
        self, fan_speed: int = DEFAULT_FAN_SPEED_AWAY
    ) -> bool:
        """Set the fan speed in percent for the Away profile."""
        _LOGGER.debug("Setting Away fan speed to: %d%%", fan_speed)

        try:
            await self._client.set_values(
                {METRIC_KEY_PROFILE_FAN_SPEED_AWAY: fan_speed}
            )
            return True

        except (OSError, ValloxApiException) as err:
            _LOGGER.error("Error setting fan speed for Away profile: %s", err)
            return False

    async def async_set_profile_fan_speed_boost(
        self, fan_speed: int = DEFAULT_FAN_SPEED_BOOST
    ) -> bool:
        """Set the fan speed in percent for the Boost profile."""
        _LOGGER.debug("Setting Boost fan speed to: %d%%", fan_speed)

        try:
            await self._client.set_values(
                {METRIC_KEY_PROFILE_FAN_SPEED_BOOST: fan_speed}
            )
            return True

        except (OSError, ValloxApiException) as err:
            _LOGGER.error("Error setting fan speed for Boost profile: %s", err)
            return False

    async def async_handle(self, call: ServiceCall) -> None:
        """Dispatch a service call."""
        method = SERVICE_TO_METHOD.get(call.service)
        params = call.data.copy()

        if method is None:
            return

        if not hasattr(self, method["method"]):
            _LOGGER.error("Service not implemented: %s", method["method"])
            return

        result = await getattr(self, method["method"])(**params)

        # This state change affects other entities like sensors. Force an immediate update that can
        # be observed by all parties involved.
        if result:
            await self._state_proxy.async_update()

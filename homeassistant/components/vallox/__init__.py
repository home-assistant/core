"""Support for Vallox ventilation units."""

from datetime import timedelta
import ipaddress
import logging

from vallox_websocket_api import PROFILE as VALLOX_PROFILE, Vallox
from vallox_websocket_api.constants import vlxDevConstants
from vallox_websocket_api.exceptions import ValloxApiException
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)

DOMAIN = "vallox"
DEFAULT_NAME = "Vallox"
SIGNAL_VALLOX_STATE_UPDATE = "vallox_state_update"
SCAN_INTERVAL = timedelta(seconds=60)

# Various metric keys that are reused between profiles.
METRIC_KEY_MODE = "A_CYC_MODE"
METRIC_KEY_PROFILE_FAN_SPEED_HOME = "A_CYC_HOME_SPEED_SETTING"
METRIC_KEY_PROFILE_FAN_SPEED_AWAY = "A_CYC_AWAY_SPEED_SETTING"
METRIC_KEY_PROFILE_FAN_SPEED_BOOST = "A_CYC_BOOST_SPEED_SETTING"

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

# pylint: disable=no-member
PROFILE_TO_STR_SETTABLE = {
    VALLOX_PROFILE.HOME: "Home",
    VALLOX_PROFILE.AWAY: "Away",
    VALLOX_PROFILE.BOOST: "Boost",
    VALLOX_PROFILE.FIREPLACE: "Fireplace",
}

STR_TO_PROFILE = {v: k for (k, v) in PROFILE_TO_STR_SETTABLE.items()}

# pylint: disable=no-member
PROFILE_TO_STR_REPORTABLE = {
    **{VALLOX_PROFILE.NONE: "None", VALLOX_PROFILE.EXTRA: "Extra"},
    **PROFILE_TO_STR_SETTABLE,
}

ATTR_PROFILE = "profile"
ATTR_PROFILE_FAN_SPEED = "fan_speed"

SERVICE_SCHEMA_SET_PROFILE = vol.Schema(
    {vol.Required(ATTR_PROFILE): vol.All(cv.string, vol.In(STR_TO_PROFILE))}
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

DEFAULT_FAN_SPEED_HOME = 50
DEFAULT_FAN_SPEED_AWAY = 25
DEFAULT_FAN_SPEED_BOOST = 65


async def async_setup(hass, config):
    """Set up the client and boot the platforms."""
    conf = config[DOMAIN]
    host = conf.get(CONF_HOST)
    name = conf.get(CONF_NAME)

    client = Vallox(host)
    state_proxy = ValloxStateProxy(hass, client)
    service_handler = ValloxServiceHandler(client, state_proxy)

    hass.data[DOMAIN] = {"client": client, "state_proxy": state_proxy, "name": name}

    for vallox_service in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[vallox_service]["schema"]
        hass.services.async_register(
            DOMAIN, vallox_service, service_handler.async_handle, schema=schema
        )

    # The vallox hardware expects quite strict timings for websocket
    # requests. Timings that machines with less processing power, like
    # Raspberries, cannot live up to during the busy start phase of Home
    # Asssistant. Hence, async_add_entities() for fan and sensor in respective
    # code will be called with update_before_add=False to intentionally delay
    # the first request, increasing chance that it is issued only when the
    # machine is less busy again.
    hass.async_create_task(async_load_platform(hass, "sensor", DOMAIN, {}, config))
    hass.async_create_task(async_load_platform(hass, "fan", DOMAIN, {}, config))

    async_track_time_interval(hass, state_proxy.async_update, SCAN_INTERVAL)

    return True


class ValloxStateProxy:
    """Helper class to reduce websocket API calls."""

    def __init__(self, hass, client):
        """Initialize the proxy."""
        self._hass = hass
        self._client = client
        self._metric_cache = {}
        self._profile = None
        self._valid = False

    def fetch_metric(self, metric_key):
        """Return cached state value."""
        _LOGGER.debug("Fetching metric key: %s", metric_key)

        if not self._valid:
            raise OSError("Device state out of sync.")

        if metric_key not in vlxDevConstants.__dict__:
            raise KeyError(f"Unknown metric key: {metric_key}")

        return self._metric_cache[metric_key]

    def get_profile(self):
        """Return cached profile value."""
        _LOGGER.debug("Returning profile")

        if not self._valid:
            raise OSError("Device state out of sync.")

        return PROFILE_TO_STR_REPORTABLE[self._profile]

    async def async_update(self, event_time):
        """Fetch state update."""
        _LOGGER.debug("Updating Vallox state cache")

        try:
            self._metric_cache = await self._client.fetch_metrics()
            self._profile = await self._client.get_profile()
            self._valid = True

        except (OSError, ValloxApiException) as err:
            _LOGGER.error("Error during state cache update: %s", err)
            self._valid = False

        async_dispatcher_send(self._hass, SIGNAL_VALLOX_STATE_UPDATE)


class ValloxServiceHandler:
    """Services implementation."""

    def __init__(self, client, state_proxy):
        """Initialize the proxy."""
        self._client = client
        self._state_proxy = state_proxy

    async def async_set_profile(self, profile: str = "Home") -> bool:
        """Set the ventilation profile."""
        _LOGGER.debug("Setting ventilation profile to: %s", profile)

        try:
            await self._client.set_profile(STR_TO_PROFILE[profile])
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
        """Set the fan speed in percent for the Home profile."""
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

    async def async_handle(self, service):
        """Dispatch a service call."""
        method = SERVICE_TO_METHOD.get(service.service)
        params = service.data.copy()

        if not hasattr(self, method["method"]):
            _LOGGER.error("Service not implemented: %s", method["method"])
            return

        result = await getattr(self, method["method"])(**params)

        # Force state_proxy to refresh device state, so that updates are
        # propagated to platforms.
        if result:
            await self._state_proxy.async_update(None)

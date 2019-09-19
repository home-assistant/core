"""Support for a Genius Hub system."""
from datetime import timedelta
import logging
import re
from typing import Any, Awaitable, Dict, Optional

import aiohttp
import voluptuous as vol

from geniushubclient import GeniusHub

from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
    TEMP_CELSIUS,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import (
    async_dispatcher_send,
    async_dispatcher_connect,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.dt import utc_from_timestamp

ATTR_DURATION = "duration"

_LOGGER = logging.getLogger(__name__)

DOMAIN = "geniushub"

# temperature is repeated here, as it gives access to high-precision temps
GH_STATE_ATTRS = ["mode", "temperature", "type", "occupied", "override"]

SCAN_INTERVAL = timedelta(seconds=60)

_V1_API_SCHEMA = vol.Schema({vol.Required(CONF_TOKEN): cv.string})
_V3_API_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)
CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Any(_V3_API_SCHEMA, _V1_API_SCHEMA)}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass, hass_config):
    """Create a Genius Hub system."""
    kwargs = dict(hass_config[DOMAIN])
    if CONF_HOST in kwargs:
        args = (kwargs.pop(CONF_HOST),)
    else:
        args = (kwargs.pop(CONF_TOKEN),)

    hass.data[DOMAIN] = {}
    broker = GeniusBroker(hass, args, kwargs)

    try:
        await broker.client.update()
    except aiohttp.ClientResponseError as err:
        _LOGGER.error("Setup failed, check your configuration, %s", err)
        return False
    broker.make_debug_log_entries()

    async_track_time_interval(hass, broker.async_update, SCAN_INTERVAL)

    for platform in ["climate", "water_heater"]:
        hass.async_create_task(
            async_load_platform(hass, platform, DOMAIN, {}, hass_config)
        )

    if broker.client.api_version == 3:  # pylint: disable=no-member
        for platform in ["sensor", "binary_sensor"]:
            hass.async_create_task(
                async_load_platform(hass, platform, DOMAIN, {}, hass_config)
            )

    return True


class GeniusBroker:
    """Container for geniushub client and data."""

    def __init__(self, hass, args, kwargs):
        """Initialize the geniushub client."""
        self.hass = hass
        self.client = hass.data[DOMAIN]["client"] = GeniusHub(
            *args, **kwargs, session=async_get_clientsession(hass)
        )

    async def async_update(self, now, **kwargs):
        """Update the geniushub client's data."""
        try:
            await self.client.update()
        except aiohttp.ClientResponseError as err:
            _LOGGER.warning("Update failed, message is: %s", err)
            return
        self.make_debug_log_entries()

        async_dispatcher_send(self.hass, DOMAIN)

    def make_debug_log_entries(self):
        """Make any useful debug log entries."""
        # pylint: disable=protected-access
        _LOGGER.debug(
            "Raw JSON: \n\nclient._zones = %s \n\nclient._devices = %s",
            self.client._zones,
            self.client._devices,
        )


class GeniusEntity(Entity):
    """Base for all Genius Hub entities."""

    def __init__(self):
        """Initialize the entity."""
        self._name = None

    async def async_added_to_hass(self) -> Awaitable[None]:
        """Set up a listener when this entity is added to HA."""
        async_dispatcher_connect(self.hass, DOMAIN, self._refresh)

    @callback
    def _refresh(self) -> None:
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def name(self) -> str:
        """Return the name of the geniushub entity."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """Return False as geniushub entities should not be polled."""
        return False


class GeniusDevice(GeniusEntity):
    """Base for all Genius Hub devices."""

    def __init__(self):
        """Initialize the device."""
        super().__init__()

        self._state_attr = None
        self._last_comms = None

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the device state attributes."""

        def snake_case(string):
            """Convert a string to snake_case."""
            string = re.sub(r"[\-\.\s]", "_", str(string))
            return (string[0]).lower() + re.sub(
                r"[A-Z]", lambda matched: "_" + matched.group(0).lower(), string[1:]
            )

        attrs = {}
        attrs["assigned_zone"] = self._device.data["assignedZones"][0]["name"]
        attrs["last_comms"] = (
            None
            if self._last_comms == 0
            else utc_from_timestamp(self._last_comms).isoformat()
        )

        state = dict(self._device.data["state"])
        state.update(self._device.data["_state"])
        state.pop(self._state_attr)
        state.pop("lastComms")

        attrs["state"] = {snake_case(k): v for k, v in state.items()}

        return attrs

    async def async_update(self) -> Awaitable[None]:
        """Update an entity's state data."""
        self._last_comms = self._device.data["_state"]["lastComms"]


class GeniusZone(GeniusEntity):
    """Base for all Genius Hub zones."""

    def __init__(self):
        """Initialize the zone."""
        super().__init__()

    @property
    def name(self) -> str:
        """Return the name of the climate device."""
        return self._zone.name

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the device state attributes."""
        tmp = self._zone.data.items()
        return {"status": {k: v for k, v in tmp if k in GH_STATE_ATTRS}}

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self._zone.data.get("temperature")

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return self._zone.data["setpoint"]

    @property
    def min_temp(self) -> float:
        """Return max valid temperature that can be set."""
        return self._min_temp

    @property
    def max_temp(self) -> float:
        """Return max valid temperature that can be set."""
        return self._max_temp

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def supported_features(self) -> int:
        """Return the bitmask of supported features."""
        return self._supported_features

    async def async_set_temperature(self, **kwargs) -> Awaitable[None]:
        """Set a new target temperature for this zone."""
        await self._zone.set_override(
            kwargs[ATTR_TEMPERATURE], kwargs.get(ATTR_DURATION, 3600)
        )

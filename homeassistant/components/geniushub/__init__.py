"""Support for a Genius Hub system."""
from datetime import timedelta
import logging
from typing import Any, Dict, Optional

import aiohttp
from geniushubclient import GeniusHub
import voluptuous as vol

from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_MAC,
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
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
import homeassistant.util.dt as dt_util

ATTR_DURATION = "duration"

_LOGGER = logging.getLogger(__name__)

DOMAIN = "geniushub"

# temperature is repeated here, as it gives access to high-precision temps
GH_ZONE_ATTRS = ["mode", "temperature", "type", "occupied", "override"]
GH_DEVICE_ATTRS = {
    "luminance": "luminance",
    "measuredTemperature": "measured_temperature",
    "occupancyTrigger": "occupancy_trigger",
    "setback": "setback",
    "setTemperature": "set_temperature",
    "wakeupInterval": "wakeup_interval",
}

SCAN_INTERVAL = timedelta(seconds=60)

MAC_ADDRESS_REGEXP = r"^([0-9A-F]{2}:){5}([0-9A-F]{2})$"

V1_API_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Required(CONF_MAC): vol.Match(MAC_ADDRESS_REGEXP),
    }
)
V3_API_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_MAC): vol.Match(MAC_ADDRESS_REGEXP),
    }
)
CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Any(V3_API_SCHEMA, V1_API_SCHEMA)}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Create a Genius Hub system."""
    hass.data[DOMAIN] = {}

    kwargs = dict(config[DOMAIN])
    if CONF_HOST in kwargs:
        args = (kwargs.pop(CONF_HOST),)
    else:
        args = (kwargs.pop(CONF_TOKEN),)
    hub_uid = kwargs.pop(CONF_MAC, None)

    client = GeniusHub(*args, **kwargs, session=async_get_clientsession(hass))

    broker = hass.data[DOMAIN]["broker"] = GeniusBroker(hass, client, hub_uid)

    try:
        await client.update()
    except aiohttp.ClientResponseError as err:
        _LOGGER.error("Setup failed, check your configuration, %s", err)
        return False
    broker.make_debug_log_entries()

    async_track_time_interval(hass, broker.async_update, SCAN_INTERVAL)

    for platform in ["climate", "water_heater", "sensor", "binary_sensor", "switch"]:
        hass.async_create_task(async_load_platform(hass, platform, DOMAIN, {}, config))

    return True


class GeniusBroker:
    """Container for geniushub client and data."""

    def __init__(self, hass, client, hub_uid) -> None:
        """Initialize the geniushub client."""
        self.hass = hass
        self.client = client
        self._hub_uid = hub_uid

    @property
    def hub_uid(self) -> int:
        """Return the Hub UID (MAC address)."""
        # pylint: disable=no-member
        return self._hub_uid if self._hub_uid is not None else self.client.uid

    async def async_update(self, now, **kwargs) -> None:
        """Update the geniushub client's data."""
        try:
            await self.client.update()
        except aiohttp.ClientResponseError as err:
            _LOGGER.warning("Update failed, message is: %s", err)
            return
        self.make_debug_log_entries()

        async_dispatcher_send(self.hass, DOMAIN)

    def make_debug_log_entries(self) -> None:
        """Make any useful debug log entries."""
        # pylint: disable=protected-access
        _LOGGER.debug(
            "Raw JSON: \n\nclient._zones = %s \n\nclient._devices = %s",
            self.client._zones,
            self.client._devices,
        )


class GeniusEntity(Entity):
    """Base for all Genius Hub entities."""

    def __init__(self) -> None:
        """Initialize the entity."""
        self._unique_id = self._name = None

    async def async_added_to_hass(self) -> None:
        """Set up a listener when this entity is added to HA."""
        async_dispatcher_connect(self.hass, DOMAIN, self._refresh)

    @callback
    def _refresh(self) -> None:
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return self._unique_id

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

    def __init__(self, broker, device) -> None:
        """Initialize the Device."""
        super().__init__()

        self._device = device
        self._unique_id = f"{broker.hub_uid}_device_{device.id}"

        self._last_comms = self._state_attr = None

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the device state attributes."""

        attrs = {}
        attrs["assigned_zone"] = self._device.data["assignedZones"][0]["name"]
        if self._last_comms:
            attrs["last_comms"] = self._last_comms.isoformat()

        state = dict(self._device.data["state"])
        if "_state" in self._device.data:  # only for v3 API
            state.update(self._device.data["_state"])

        attrs["state"] = {
            GH_DEVICE_ATTRS[k]: v for k, v in state.items() if k in GH_DEVICE_ATTRS
        }

        return attrs

    async def async_update(self) -> None:
        """Update an entity's state data."""
        if "_state" in self._device.data:  # only for v3 API
            self._last_comms = dt_util.utc_from_timestamp(
                self._device.data["_state"]["lastComms"]
            )


class GeniusZone(GeniusEntity):
    """Base for all Genius Hub zones."""

    def __init__(self, broker, zone) -> None:
        """Initialize the Zone."""
        super().__init__()

        self._zone = zone
        self._unique_id = f"{broker.hub_uid}_zone_{zone.id}"

    @property
    def name(self) -> str:
        """Return the name of the climate device."""
        return self._zone.name

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the device state attributes."""
        status = {k: v for k, v in self._zone.data.items() if k in GH_ZONE_ATTRS}
        return {"status": status}


class GeniusHeatingZone(GeniusZone):
    """Base for Genius Heating Zones."""

    def __init__(self, broker, zone) -> None:
        """Initialize the Zone."""
        super().__init__(broker, zone)

        self._max_temp = self._min_temp = self._supported_features = None

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

    async def async_set_temperature(self, **kwargs) -> None:
        """Set a new target temperature for this zone."""
        await self._zone.set_override(
            kwargs[ATTR_TEMPERATURE], kwargs.get(ATTR_DURATION, 3600)
        )

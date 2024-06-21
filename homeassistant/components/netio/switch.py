"""The Netio switch component."""

from __future__ import annotations

from collections import namedtuple
from datetime import timedelta
import logging
from typing import Any

from pynetio import Netio
import voluptuous as vol

from homeassistant import util
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

ATTR_START_DATE = "start_date"
ATTR_TOTAL_CONSUMPTION_KWH = "total_energy_kwh"

CONF_OUTLETS = "outlets"

DEFAULT_PORT = 1234
DEFAULT_USERNAME = "admin"
Device = namedtuple("Device", ["netio", "entities"])
DEVICES: dict[str, Device] = {}

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

REQ_CONF = [CONF_HOST, CONF_OUTLETS]

URL_API_NETIO_EP = "/api/netio/{host}"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_OUTLETS): {cv.string: cv.string},
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Netio platform."""

    host = config[CONF_HOST]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    port = config[CONF_PORT]

    if not DEVICES:
        hass.http.register_view(NetioApiView)

    dev = Netio(host, port, username, password)

    DEVICES[host] = Device(dev, [])

    # Throttle the update for all Netio switches of one Netio
    dev.update = util.Throttle(MIN_TIME_BETWEEN_SCANS)(dev.update)

    for key in config[CONF_OUTLETS]:
        switch = NetioSwitch(DEVICES[host].netio, key, config[CONF_OUTLETS][key])
        DEVICES[host].entities.append(switch)

    add_entities(DEVICES[host].entities)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, dispose)


def dispose(event):
    """Close connections to Netio Devices."""
    for value in DEVICES.values():
        value.netio.stop()


class NetioApiView(HomeAssistantView):
    """WSGI handler class."""

    url = URL_API_NETIO_EP
    name = "api:netio"

    @callback
    def get(self, request, host):
        """Request handler."""
        data = request.query
        states, consumptions, cumulated_consumptions, start_dates = [], [], [], []

        for i in range(1, 5):
            out = "output%d" % i
            states.append(data.get(f"{out}_state") == STATE_ON)
            consumptions.append(float(data.get(f"{out}_consumption", 0)))
            cumulated_consumptions.append(
                float(data.get(f"{out}_cumulatedConsumption", 0)) / 1000
            )
            start_dates.append(data.get(f"{out}_consumptionStart", ""))

        _LOGGER.debug(
            "%s: %s, %s, %s since %s",
            host,
            states,
            consumptions,
            cumulated_consumptions,
            start_dates,
        )

        ndev = DEVICES[host].netio
        ndev.consumptions = consumptions
        ndev.cumulated_consumptions = cumulated_consumptions
        ndev.states = states
        ndev.start_dates = start_dates

        for dev in DEVICES[host].entities:
            dev.async_write_ha_state()

        return self.json(True)


class NetioSwitch(SwitchEntity):
    """Provide a Netio linked switch."""

    def __init__(self, netio, outlet, name):
        """Initialize the Netio switch."""
        self._name = name
        self.outlet = outlet
        self.netio = netio

    @property
    def name(self):
        """Return the device's name."""
        return self._name

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        return not hasattr(self, "telnet")

    def turn_on(self, **kwargs: Any) -> None:
        """Turn switch on."""
        self._set(True)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn switch off."""
        self._set(False)

    def _set(self, value):
        val = list("uuuu")
        val[int(self.outlet) - 1] = "1" if value else "0"
        self.netio.get("port list {}".format("".join(val)))
        self.netio.states[int(self.outlet) - 1] = value
        self.schedule_update_ha_state()

    @property
    def is_on(self):
        """Return the switch's status."""
        return self.netio.states[int(self.outlet) - 1]

    def update(self) -> None:
        """Update the state."""
        self.netio.update()

"""Support for Huawei LTE sensors."""

import logging
import re
from typing import Optional

import attr
import voluptuous as vol

from homeassistant.const import CONF_URL, CONF_MONITORED_CONDITIONS, STATE_UNKNOWN
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    DEVICE_CLASS_SIGNAL_STRENGTH,
)
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

from . import RouterData
from .const import (
    DOMAIN,
    KEY_DEVICE_INFORMATION,
    KEY_DEVICE_SIGNAL,
    KEY_MONITORING_TRAFFIC_STATISTICS,
)


_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME_TEMPLATE = "Huawei {} {}"
DEFAULT_DEVICE_NAME = "LTE"

DEFAULT_SENSORS = [
    f"{KEY_DEVICE_INFORMATION}.WanIPAddress",
    f"{KEY_DEVICE_SIGNAL}.rsrq",
    f"{KEY_DEVICE_SIGNAL}.rsrp",
    f"{KEY_DEVICE_SIGNAL}.rssi",
    f"{KEY_DEVICE_SIGNAL}.sinr",
]

SENSOR_META = {
    f"{KEY_DEVICE_INFORMATION}.SoftwareVersion": dict(name="Software version"),
    f"{KEY_DEVICE_INFORMATION}.WanIPAddress": dict(
        name="WAN IP address", icon="mdi:ip"
    ),
    f"{KEY_DEVICE_INFORMATION}.WanIPv6Address": dict(
        name="WAN IPv6 address", icon="mdi:ip"
    ),
    f"{KEY_DEVICE_SIGNAL}.band": dict(name="Band"),
    f"{KEY_DEVICE_SIGNAL}.cell_id": dict(name="Cell ID"),
    f"{KEY_DEVICE_SIGNAL}.lac": dict(name="LAC"),
    f"{KEY_DEVICE_SIGNAL}.mode": dict(
        name="Mode",
        formatter=lambda x: ({"0": "2G", "2": "3G", "7": "4G"}.get(x, "Unknown"), None),
    ),
    f"{KEY_DEVICE_SIGNAL}.pci": dict(name="PCI"),
    f"{KEY_DEVICE_SIGNAL}.rsrq": dict(
        name="RSRQ",
        device_class=DEVICE_CLASS_SIGNAL_STRENGTH,
        # http://www.lte-anbieter.info/technik/rsrq.php
        icon=lambda x: (x is None or x < -11)
        and "mdi:signal-cellular-outline"
        or x < -8
        and "mdi:signal-cellular-1"
        or x < -5
        and "mdi:signal-cellular-2"
        or "mdi:signal-cellular-3",
    ),
    f"{KEY_DEVICE_SIGNAL}.rsrp": dict(
        name="RSRP",
        device_class=DEVICE_CLASS_SIGNAL_STRENGTH,
        # http://www.lte-anbieter.info/technik/rsrp.php
        icon=lambda x: (x is None or x < -110)
        and "mdi:signal-cellular-outline"
        or x < -95
        and "mdi:signal-cellular-1"
        or x < -80
        and "mdi:signal-cellular-2"
        or "mdi:signal-cellular-3",
    ),
    f"{KEY_DEVICE_SIGNAL}.rssi": dict(
        name="RSSI",
        device_class=DEVICE_CLASS_SIGNAL_STRENGTH,
        # https://eyesaas.com/wi-fi-signal-strength/
        icon=lambda x: (x is None or x < -80)
        and "mdi:signal-cellular-outline"
        or x < -70
        and "mdi:signal-cellular-1"
        or x < -60
        and "mdi:signal-cellular-2"
        or "mdi:signal-cellular-3",
    ),
    f"{KEY_DEVICE_SIGNAL}.sinr": dict(
        name="SINR",
        device_class=DEVICE_CLASS_SIGNAL_STRENGTH,
        # http://www.lte-anbieter.info/technik/sinr.php
        icon=lambda x: (x is None or x < 0)
        and "mdi:signal-cellular-outline"
        or x < 5
        and "mdi:signal-cellular-1"
        or x < 10
        and "mdi:signal-cellular-2"
        or "mdi:signal-cellular-3",
    ),
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_URL): cv.url,
        vol.Optional(
            CONF_MONITORED_CONDITIONS, default=DEFAULT_SENSORS
        ): cv.ensure_list,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Huawei LTE sensor devices."""
    data = hass.data[DOMAIN].get_data(config)
    sensors = []
    for path in config.get(CONF_MONITORED_CONDITIONS):
        if path == "traffic_statistics":  # backwards compatibility
            path = KEY_MONITORING_TRAFFIC_STATISTICS
        data.subscribe(path)
        sensors.append(HuaweiLteSensor(data, path, SENSOR_META.get(path, {})))

    # Pre-0.97 unique id migration. Old ones used the device serial number
    # (see comments in HuaweiLteData._setup_lte for more info), as well as
    # had a bug that joined the path str with periods, not the path components,
    # resulting e.g. *_device_signal.sinr to end up as
    # *_d.e.v.i.c.e._.s.i.g.n.a.l...s.i.n.r
    entreg = await entity_registry.async_get_registry(hass)
    for entid, ent in entreg.entities.items():
        if ent.platform != DOMAIN:
            continue
        for sensor in sensors:
            oldsuf = ".".join(sensor.path)
            if ent.unique_id.endswith(f"_{oldsuf}"):
                entreg.async_update_entity(entid, new_unique_id=sensor.unique_id)
                _LOGGER.debug(
                    "Updated entity %s unique id to %s", entid, sensor.unique_id
                )

    async_add_entities(sensors, True)


def format_default(value):
    """Format value."""
    unit = None
    if value is not None:
        # Clean up value and infer unit, e.g. -71dBm, 15 dB
        match = re.match(
            r"([>=<]*)(?P<value>.+?)\s*(?P<unit>[a-zA-Z]+)\s*$", str(value)
        )
        if match:
            try:
                value = float(match.group("value"))
                unit = match.group("unit")
            except ValueError:
                pass
    return value, unit


@attr.s
class HuaweiLteSensor(Entity):
    """Huawei LTE sensor entity."""

    data = attr.ib(type=RouterData)
    path = attr.ib(type=str)
    meta = attr.ib(type=dict)

    _state = attr.ib(init=False, default=STATE_UNKNOWN)
    _unit = attr.ib(init=False, type=str)

    @property
    def unique_id(self) -> str:
        """Return unique ID for sensor."""
        return f"{self.data.mac}-{self.path}"

    @property
    def name(self) -> str:
        """Return sensor name."""
        try:
            dname = self.data[f"{KEY_DEVICE_INFORMATION}.DeviceName"]
        except KeyError:
            dname = None
        vname = self.meta.get("name", self.path)
        return DEFAULT_NAME_TEMPLATE.format(dname or DEFAULT_DEVICE_NAME, vname)

    @property
    def state(self):
        """Return sensor state."""
        return self._state

    @property
    def device_class(self) -> Optional[str]:
        """Return sensor device class."""
        return self.meta.get("device_class")

    @property
    def unit_of_measurement(self):
        """Return sensor's unit of measurement."""
        return self.meta.get("unit", self._unit)

    @property
    def icon(self):
        """Return icon for sensor."""
        icon = self.meta.get("icon")
        if callable(icon):
            return icon(self.state)
        return icon

    def update(self):
        """Update state."""
        self.data.update()

        try:
            value = self.data[self.path]
        except KeyError:
            _LOGGER.debug("%s not in data", self.path)
            value = None

        formatter = self.meta.get("formatter")
        if not callable(formatter):
            formatter = format_default

        self._state, self._unit = formatter(value)

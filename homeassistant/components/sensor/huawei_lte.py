"""Huawei LTE sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.huawei_lte/
"""

import logging
import re

import attr
import voluptuous as vol

from homeassistant.const import (
    CONF_URL, CONF_MONITORED_CONDITIONS, STATE_UNKNOWN,
)
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

from ..huawei_lte import DATA_KEY, RouterData


_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['huawei_lte']

DEFAULT_NAME_TEMPLATE = 'Huawei {}: {}'

DEFAULT_SENSORS = [
    "device_information.WanIPAddress",
    "device_signal.rssi",
]

SENSOR_META = {
    "device_information.SoftwareVersion": dict(
        name="Software version",
    ),
    "device_information.WanIPAddress": dict(
        name="WAN IP address",
        icon="mdi:ip",
    ),
    "device_information.WanIPv6Address": dict(
        name="WAN IPv6 address",
        icon="mdi:ip",
    ),
    "device_signal.rsrq": dict(
        name="RSRQ",
        # http://www.lte-anbieter.info/technik/rsrq.php
        icon=lambda x:
        x >= -5 and "mdi:signal-cellular-3"
        or x >= -8 and "mdi:signal-cellular-2"
        or x >= -11 and "mdi:signal-cellular-1"
        or "mdi:signal-cellular-outline"
    ),
    "device_signal.rsrp": dict(
        name="RSRP",
        # http://www.lte-anbieter.info/technik/rsrp.php
        icon=lambda x:
        x >= -80 and "mdi:signal-cellular-3"
        or x >= -95 and "mdi:signal-cellular-2"
        or x >= -110 and "mdi:signal-cellular-1"
        or "mdi:signal-cellular-outline"
    ),
    "device_signal.rssi": dict(
        name="RSSI",
        # https://eyesaas.com/wi-fi-signal-strength/
        icon=lambda x:
        x >= -60 and "mdi:signal-cellular-3"
        or x >= -70 and "mdi:signal-cellular-2"
        or x >= -80 and "mdi:signal-cellular-1"
        or "mdi:signal-cellular-outline"
    ),
    "device_signal.sinr": dict(
        name="SINR",
        # http://www.lte-anbieter.info/technik/sinr.php
        icon=lambda x:
        x >= 10 and "mdi:signal-cellular-3"
        or x >= 5 and "mdi:signal-cellular-2"
        or x >= 0 and "mdi:signal-cellular-1"
        or "mdi:signal-cellular-outline"
    ),
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_URL): cv.url,
    vol.Optional(
        CONF_MONITORED_CONDITIONS, default=DEFAULT_SENSORS): cv.ensure_list,
})


def setup_platform(
        hass, config, add_entities, discovery_info):
    """Set up Huawei LTE sensor devices."""
    data = hass.data[DATA_KEY].get_data(config)
    sensors = []
    for path in config.get(CONF_MONITORED_CONDITIONS):
        sensors.append(HuaweiLteSensor(
            data, path, SENSOR_META.get(path, {})))
    add_entities(sensors, True)


@attr.s
class HuaweiLteSensor(Entity):
    """Huawei LTE sensor entity."""

    data = attr.ib(type=RouterData)
    path = attr.ib(type=list)
    meta = attr.ib(type=dict)

    _state = attr.ib(init=False, default=STATE_UNKNOWN)
    _unit = attr.ib(init=False, type=str)

    @property
    def unique_id(self) -> str:
        """Return unique ID for sensor."""
        return "{}_{}".format(
            self.path,
            self.data["device_information.SerialNumber"],
        )

    @property
    def name(self) -> str:
        """Return sensor name."""
        dname = self.data["device_information.DeviceName"]
        vname = self.meta.get("name", self.path)
        return DEFAULT_NAME_TEMPLATE.format(dname, vname)

    @property
    def state(self):
        """Return sensor state."""
        return self._state

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

        unit = None
        try:
            value = self.data[self.path]
        except KeyError:
            _LOGGER.warning("%s not in data", self.path)
            value = None

        if value is not None:
            # Clean up value and infer unit, e.g. -71dBm, 15 dB
            match = re.match(
                r"(?P<value>.+?)\s*(?P<unit>[a-zA-Z]+)\s*$", str(value))
            if match:
                try:
                    value = float(match.group("value"))
                    unit = match.group("unit")
                except ValueError:
                    pass

        self._state = value
        self._unit = unit

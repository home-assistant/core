"""Support for Xiaomi Gateways."""

from datetime import timedelta
import logging
from typing import Any

from homeassistant.const import ATTR_BATTERY_LEVEL, ATTR_VOLTAGE, CONF_MAC
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

TIME_TILL_UNAVAILABLE = timedelta(minutes=150)


class XiaomiDevice(Entity):
    """Representation a base Xiaomi device."""

    _attr_should_poll = False

    def __init__(self, device, device_type, xiaomi_hub, config_entry):
        """Initialize the Xiaomi device."""
        self._state = None
        self._is_available = True
        self._sid = device["sid"]
        self._model = device["model"]
        self._protocol = device["proto"]
        self._name = f"{device_type}_{self._sid}"
        self._device_name = f"{self._model}_{self._sid}"
        self._type = device_type
        self._write_to_hub = xiaomi_hub.write_to_hub
        self._get_from_hub = xiaomi_hub.get_from_hub
        self._extra_state_attributes = {}
        self._remove_unavailability_tracker = None
        self._xiaomi_hub = xiaomi_hub
        self.parse_data(device["data"], device["raw_data"])
        self.parse_voltage(device["data"])

        if hasattr(self, "_data_key") and self._data_key:
            self._unique_id = f"{self._data_key}{self._sid}"
        else:
            self._unique_id = f"{self._type}{self._sid}"

        self._gateway_id = config_entry.unique_id
        if config_entry.data[CONF_MAC] == format_mac(self._sid):
            # this entity belongs to the gateway itself
            self._is_gateway = True
            self._device_id = config_entry.unique_id
        else:
            # this entity is connected through zigbee
            self._is_gateway = False
            self._device_id = self._sid

    async def async_added_to_hass(self) -> None:
        """Start unavailability tracking."""
        self._xiaomi_hub.callbacks[self._sid].append(self.push_data)
        self._async_track_unavailable()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_id(self):
        """Return the device id of the Xiaomi Aqara device."""
        return self._device_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info of the Xiaomi Aqara device."""
        if self._is_gateway:
            device_info = DeviceInfo(
                identifiers={(DOMAIN, self._device_id)},
                connections={(dr.CONNECTION_NETWORK_MAC, self._device_id)},
                model=self._model,
            )
        else:
            device_info = DeviceInfo(
                connections={(dr.CONNECTION_ZIGBEE, self._device_id)},
                identifiers={(DOMAIN, self._device_id)},
                manufacturer="Xiaomi Aqara",
                model=self._model,
                name=self._device_name,
                sw_version=self._protocol,
                via_device=(DOMAIN, self._gateway_id),
            )

        return device_info

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._is_available

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._extra_state_attributes

    @callback
    def _async_set_unavailable(self, now):
        """Set state to UNAVAILABLE."""
        self._remove_unavailability_tracker = None
        self._is_available = False
        self.async_write_ha_state()

    @callback
    def _async_track_unavailable(self):
        if self._remove_unavailability_tracker:
            self._remove_unavailability_tracker()
        self._remove_unavailability_tracker = async_track_point_in_utc_time(
            self.hass, self._async_set_unavailable, utcnow() + TIME_TILL_UNAVAILABLE
        )
        if not self._is_available:
            self._is_available = True
            return True
        return False

    def push_data(self, data: dict[str, Any], raw_data: dict[Any, Any]) -> None:
        """Push from Hub running in another thread."""
        self.hass.loop.call_soon_threadsafe(self.async_push_data, data, raw_data)

    @callback
    def async_push_data(self, data: dict[str, Any], raw_data: dict[Any, Any]) -> None:
        """Push from Hub handled in the event loop."""
        _LOGGER.debug("PUSH >> %s: %s", self, data)
        was_unavailable = self._async_track_unavailable()
        is_data = self.parse_data(data, raw_data)
        is_voltage = self.parse_voltage(data)
        if is_data or is_voltage or was_unavailable:
            self.async_write_ha_state()

    def parse_voltage(self, data):
        """Parse battery level data sent by gateway."""
        if "voltage" in data:
            voltage_key = "voltage"
        elif "battery_voltage" in data:
            voltage_key = "battery_voltage"
        else:
            return False

        max_volt = 3300
        min_volt = 2800
        voltage = data[voltage_key]
        self._extra_state_attributes[ATTR_VOLTAGE] = round(voltage / 1000.0, 2)
        voltage = min(voltage, max_volt)
        voltage = max(voltage, min_volt)
        percent = ((voltage - min_volt) / (max_volt - min_volt)) * 100
        self._extra_state_attributes[ATTR_BATTERY_LEVEL] = round(percent, 1)
        return True

    def parse_data(self, data, raw_data):
        """Parse data sent by gateway."""
        raise NotImplementedError

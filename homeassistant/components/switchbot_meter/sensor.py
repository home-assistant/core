"""Support for Switchbot temperature/humidity Bluetooth LE sensors."""
import logging
from datetime import timedelta
import re

from bluepy.btle import (  # pylint: disable=import-error, no-member, no-name-in-module
    Scanner,
)
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MAC,
    CONF_NAME,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from . import DOMAIN, DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=2)  # SwitchBot Meter update its reading every 2min

SWITCHBOT_UUID = "cba20d00-224d-11e6-9fb8-0002a5d5c51b"

SKIP_HANDLE_LOOKUP = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MAC): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Switchbot Meter sensor."""
    _LOGGER.debug("Setting up...")
    name = config.get(CONF_NAME)
    if not name:
        name = DEFAULT_NAME

    mac = config.get(CONF_MAC)
    if not mac or not re.match(
        "[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", mac.lower()
    ):
        _LOGGER.error("Need a valid MAC address")
        return

    scanner = SwitchbotScanner(mac)
    add_entities(
        [
            SwitchbotMeter(
                mac,
                scanner,
                DEVICE_CLASS_TEMPERATURE,
                f"{name} Temperature",
                TEMP_CELSIUS,
            )
        ]
    )
    add_entities(
        [
            SwitchbotMeter(
                mac, scanner, DEVICE_CLASS_HUMIDITY, f"{name} Humidity", PERCENTAGE
            )
        ]
    )


class SwitchbotMeter(Entity):
    """Representation of a Switchbot Meter sensor."""

    def __init__(self, mac, scanner, device, name, unit):
        """Initialize a sensor."""
        self._scanner = scanner
        self._device = device
        self._name = name
        self._unit = unit
        if self._device == DEVICE_CLASS_TEMPERATURE:
            self._unique_id = "t_" + mac
        else:
            self._unique_id = "h_" + mac
        self._state = None
        self._errored = False

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self) -> float:
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        """Return the units of measurement."""
        return self._unit

    @property
    def device_class(self):
        """Device class of this entity."""
        return self._device

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def icon(self) -> str:
        """Icon to use in the frontend."""
        if self._device == DEVICE_CLASS_TEMPERATURE:
            return "hass:thermometer"
        else:
            return "mdi:water-percent"

    @property
    def available(self) -> bool:
        """Return if the device is currently available."""
        return not self._errored

    def update(self):
        """Update current conditions."""
        status_ok = self._scanner.update()
        self._state = self._scanner.get_value(self._device)
        if self._state is None or not status_ok:
            _LOGGER.warning("Could not get data for %s", self._device)
            self._errored = True
        if status_ok and not self._errored:
            _LOGGER.warning("Getting back value from %s", self._device)
            self._errored = False


class SwitchbotScanner:
    """Switchbot BLE Scanner."""

    def __init__(self, mac):
        """Init Switchbot BLE scanner."""
        self._mac = mac
        self._temperature = None
        self._humidity = None

    def get_value(self, device):
        """Return the date from the device class."""
        if device == DEVICE_CLASS_TEMPERATURE:
            return self._temperature
        if device == DEVICE_CLASS_HUMIDITY:
            return self._humidity

    def update(self):
        """Update Switchbot Meter reading."""
        scanner = Scanner()
        devices = scanner.scan(5.0)
        _LOGGER.debug("Start scanning ...")

        match_uuid = False
        for dev in devices:
            if dev.addr == self._mac:
                _LOGGER.debug("Got mac")
                for (_, desc, value) in dev.getScanData():
                    if desc == "16b Service Data":
                        if len(value) == 16:
                            temp_fra = int(value[11:12].encode("utf-8"), 16) / 10.0
                            temp_int = int(value[12:14].encode("utf-8"), 16)
                            if temp_int < 128:
                                temp_int *= -1
                                temp_fra *= -1
                            else:
                                temp_int -= 128
                            meter_temp = temp_int + temp_fra
                            meter_humi = int(value[14:16].encode("utf-8"), 16) % 128
                        else:
                            meter_temp = 0
                            meter_humi = 0
                    elif desc == "Complete 128b Services" and value == SWITCHBOT_UUID:
                        match_uuid = True

        if match_uuid:
            self._temperature = meter_temp
            self._humidity = meter_humi
            return True
        else:
            _LOGGER.debug("Could not get data for %s", self._mac)
            return False

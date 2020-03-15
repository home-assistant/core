"""Support for Nexia / Trane XL Thermostats."""

import datetime

from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    ATTR_ATTRIBUTION,
)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from . import (
    ATTR_MODEL,
    ATTR_FIRMWARE,
    ATTR_THERMOSTAT_NAME,
    ATTR_THERMOSTAT_ID,
    ATTR_ZONE_ID,
    ATTRIBUTION,
    DATA_NEXIA,
    NEXIA_DEVICE,
    NEXIA_SCAN_INTERVAL,
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up sensors for a Nexia device."""
    thermostat = hass.data[DATA_NEXIA][NEXIA_DEVICE]
    scan_interval = hass.data[DATA_NEXIA][NEXIA_SCAN_INTERVAL]

    sensors = list()

    for thermostat_id in thermostat.get_thermostat_ids():
        sensors.append(
            NexiaSensor(
                thermostat,
                scan_interval,
                thermostat_id,
                "get_system_status",
                "System Status",
                None,
                None,
            )
        )

        if thermostat.has_variable_speed_compressor(thermostat_id):
            sensors.append(
                NexiaSensor(
                    thermostat,
                    scan_interval,
                    thermostat_id,
                    "get_current_compressor_speed",
                    "Current Compressor Speed",
                    None,
                    "%",
                    percent_conv,
                )
            )
            sensors.append(
                NexiaSensor(
                    thermostat,
                    scan_interval,
                    thermostat_id,
                    "get_requested_compressor_speed",
                    "Requested Compressor Speed",
                    None,
                    "%",
                    percent_conv,
                )
            )

        if thermostat.has_outdoor_temperature(thermostat_id):
            unit = (
                TEMP_CELSIUS
                if thermostat.get_unit(thermostat_id) == thermostat.UNIT_CELSIUS
                else TEMP_FAHRENHEIT
            )
            sensors.append(
                NexiaSensor(
                    thermostat,
                    scan_interval,
                    thermostat_id,
                    "get_outdoor_temperature",
                    "Outdoor Temperature",
                    DEVICE_CLASS_TEMPERATURE,
                    unit,
                )
            )

        if thermostat.has_relative_humidity(thermostat_id):
            sensors.append(
                NexiaSensor(
                    thermostat,
                    scan_interval,
                    thermostat_id,
                    "get_relative_humidity",
                    "Relative Humidity",
                    DEVICE_CLASS_HUMIDITY,
                    "%",
                    percent_conv,
                )
            )

        for zone in thermostat.get_zone_ids(thermostat_id):
            name = thermostat.get_zone_name(thermostat_id, zone)
            unit = (
                TEMP_CELSIUS
                if thermostat.get_unit(thermostat_id) == thermostat.UNIT_CELSIUS
                else TEMP_FAHRENHEIT
            )
            sensors.append(
                NexiaZoneSensor(
                    thermostat,
                    scan_interval,
                    thermostat_id,
                    zone,
                    "get_zone_temperature",
                    f"{name} Temperature",
                    DEVICE_CLASS_TEMPERATURE,
                    unit,
                    None,
                )
            )
            sensors.append(
                NexiaZoneSensor(
                    thermostat,
                    scan_interval,
                    thermostat_id,
                    zone,
                    "get_zone_status",
                    f"{name} Zone Status",
                    None,
                    None,
                )
            )
            sensors.append(
                NexiaZoneSensor(
                    thermostat,
                    scan_interval,
                    thermostat_id,
                    zone,
                    "get_zone_setpoint_status",
                    f"{name} Zone Setpoint Status",
                    None,
                    None,
                )
            )

    add_entities(sensors, True)


def percent_conv(val):
    """
    Converts an actual percentage (0.0 - 1.0) to 0-100 scale
    :param val: float (0.0 - 1.0)
    :return: val * 100.0
    """
    return val * 100.0


class NexiaSensor(Entity):
    """Provides Nexia sensor support."""

    def __init__(
        self,
        device,
        scan_interval,
        thermostat_id,
        sensor_call,
        sensor_name,
        sensor_class,
        sensor_unit,
        modifier=None,
    ):
        """Initialize the sensor."""
        self._device = device
        self._thermostat_id = thermostat_id
        self._call = sensor_call
        self._name = self._device.get_thermostat_name(thermostat_id) + " " + sensor_name
        self._class = sensor_class
        self._state = None
        self._unit_of_measurement = sensor_unit
        self._modifier = modifier
        self._scan_interval = scan_interval
        self.update = Throttle(scan_interval)(self._update)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""

        data = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_MODEL: self._device.get_thermostat_model(self._thermostat_id),
            ATTR_FIRMWARE: self._device.get_thermostat_firmware(self._thermostat_id),
            ATTR_THERMOSTAT_NAME: self._device.get_thermostat_name(self._thermostat_id),
            ATTR_THERMOSTAT_ID: self._thermostat_id,
        }
        return data

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._class

    @property
    def state(self):
        """Return the state of the sensor."""
        val = getattr(self._device, self._call)(self._thermostat_id)
        if self._modifier:
            val = self._modifier(val)
        if isinstance(val, float):
            val = round(val, 1)
        return val

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self._unit_of_measurement

    def _update(self):
        if (
            self._device.last_update is None
            or datetime.datetime.now() - self._device.last_update > self._scan_interval
        ):
            self._device.update()


class NexiaZoneSensor(NexiaSensor):
    """ Nexia Zone Sensor Support """

    def __init__(
        self,
        device,
        scan_interval,
        thermostat_id,
        zone,
        sensor_call,
        sensor_name,
        sensor_class,
        sensor_unit,
        modifier=None,
    ):
        super().__init__(
            device,
            scan_interval,
            thermostat_id,
            sensor_call,
            sensor_name,
            sensor_class,
            sensor_unit,
            modifier,
        )
        self._zone = zone

    @property
    def device_state_attributes(self):
        data = super().device_state_attributes
        data.update({ATTR_ZONE_ID: self._zone})
        return data

    @property
    def state(self):
        """Return the state of the sensor."""
        val = getattr(self._device, self._call)(self._thermostat_id, self._zone)
        if self._modifier:
            val = self._modifier(val)
        if isinstance(val, float):
            val = round(val, 1)
        return val

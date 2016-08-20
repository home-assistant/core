"""
Sensors of a KNX Device.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/knx/
"""
from knxip.conversion import knx2_to_float
from homeassistant.const import (TEMP_CELSIUS, SPEED_METERPERSECOND,
                                 ILLUMINANCE_LUX)
from homeassistant.components.knx import (KNXConfig, KNXGroupAddress)


DEPENDENCIES = ["knx"]


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Setup the KNX Sensor platform."""

    # Add KNX Temperature Sensors
    if config["type"] == 'temperature':
        add_entities([
            KNXTemperatureSensor(hass, KNXConfig(config))
        ])

    # Add KNX Speed Sensors(Like Wind Speed)
    if config["type"] == 'speed_ms':
        add_entities([
            KNXSpeedMSSensor(hass, KNXConfig(config))
        ])

    # Add KNX Speed Sensors(Like Wind Speed)
    if config["type"] == 'illuminance':
        add_entities([
            KNXIlluminanceSensor(hass, KNXConfig(config))
        ])


class KNXSensorBaseClass():  # pylint: disable=too-few-public-methods
    """
    Sensor Base Class for all KNX Sensors
    """

    @property
    def cache(self):
        """We don't want to cache any Sensor Value"""
        return False


class KNXIlluminanceSensor(KNXGroupAddress, KNXSensorBaseClass):
    """
    Representation of a KNX Group who receive KNX Lux telegrams
    by state requests.

    KNX Datapoint Type 9.004 - Lux - 2 Byte Float
    """

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._data:
            return knx2_to_float(self._data)

        return None

    @property
    def unit_of_measurement(self):
        """Type of measurement for KNX Datapoint Type 9.004 is Lux"""
        return ILLUMINANCE_LUX


class KNXSpeedMSSensor(KNXGroupAddress, KNXSensorBaseClass):
    """
    Representation of a KNX Group who receive KNX Speed telegrams
    by state requests.

    KNX Datapoint Type 9.005 - speed m/s - 2 Byte Float
    """

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._data:
            return knx2_to_float(self._data)

        return None

    @property
    def unit_of_measurement(self):
        """Type of measurement for KNX Datapoint Type 9.005 is m/s"""
        return SPEED_METERPERSECOND


class KNXTemperatureSensor(KNXGroupAddress, KNXSensorBaseClass):
    """
    Representation of a KNX Group who receive KNX Temp. telegrams
    by state requests.

    KNX Datapoint Type 9.001 - temperature - 2 Byte Float
    """

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._data:
            return knx2_to_float(self._data)

        return None

    @property
    def unit_of_measurement(self):
        """Type of measurement for KNX Datapoint Type 9.001 is C°"""
        return TEMP_CELSIUS

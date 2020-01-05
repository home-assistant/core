# Plugin created by Simon Danisch, based on the script from https://github.com/Seeed-Studio/grove.py/blob/master/grove/grove_PM2_5_HM3301.py
'''
## License

The MIT License (MIT)

Copyright (C) 2018  Seeed Technology Co.,Ltd.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
'''


"""Support for HM3301 Lazer particulate matter sensor."""
from datetime import timedelta
import logging

from smbus2 import SMBus , i2c_msg
from smbus2 import SMBusWrapper
import time
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_NAME, TEMP_FAHRENHEIT
import homeassistant.helpers.config_validation as cv

from datetime import timedelta
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "HM3301"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

HM3301_DEFAULT_I2C_ADDR = 0x40
SELECT_I2C_ADDR = 0x88
DATA_CNT = 29
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

def setup_platform(hass, config, add_entities, discovery_info=None):
    name = config.get(CONF_NAME)
    sensor = HM3301()
    dev = []
    for type in sensor.state:
        dev.append(HM3301Sensor(sensor, name, type))

    add_entities(dev, True)

class HM3301():
    """Implementation of the HM3301 sensor."""

    def __init__(self, bus_nr=1):
        """Initialize the sensor."""
        self.state = {
            "PM 1.0": 0,         # PM1.0 Standard particulate matter concentration Unit:ug/m3
            "PM 2.5": 0,         # PM2.5 Standard particulate matter concentration Unit:ug/m3
            "PM 10": 0,          # PM10  Standard particulate matter concentration Unit:ug/m3

            "PM 1.0 Atmospheric": 0,     #PM1.0 Atmospheric environment concentration ,unit:ug/m3
            "PM 2.5 Atmospheric": 0,     #PM2.5 Atmospheric environment concentration ,unit:ug/m3
            "PM 10 Atmospheric": 0,      #PM10  Atmospheric environment concentration ,unit:ug/m3
        }
        with SMBusWrapper(bus_nr) as bus:
            write = i2c_msg.write(HM3301_DEFAULT_I2C_ADDR, [SELECT_I2C_ADDR])
            bus.i2c_rdwr(write)

    def read_data(self):
        with SMBusWrapper(1) as bus:
            read = i2c_msg.read(HM3301_DEFAULT_I2C_ADDR, DATA_CNT)
            bus.i2c_rdwr(read)
            return list(read)

    def check_crc(self,data):
        sum = 0
        for i in range(DATA_CNT-1):
            sum += data[i]
        sum = sum & 0xff
        return (sum==data[28])

    def parse_data(self, data):
        self.state["PM 1.0"] = data[4]<<8 | data[5]
        self.state["PM 2.5"] = data[6]<<8 | data[7]
        self.state["PM 10"] = data[8]<<8 | data[9]

        self.state["PM 1.0 Atmospheric"] = data[10]<<8 | data[11]
        self.state["PM 2.5 Atmospheric"] = data[12]<<8 | data[13]
        self.state["PM 10 Atmospheric"] = data[14]<<8 | data[15]

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        data = self.read_data()
        #print data
        if(self.check_crc(data) != True):
            _LOGGER.error("HM3301 failed crc check while reading")
        else:
            self.parse_data(data)

class HM3301Sensor(Entity):
    """Implementation of the HM3301 sensor."""

    def __init__(self, sensor, name, type, bus_nr=1):
        """Initialize the sensor."""
        self._name = name
        self.type = type
        self.sensor = sensor

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name + " " + self.type

    @property
    def unit_of_measurement(self):
        return "µg/m³"

    @property
    def state(self):
        return self.sensor.state[self.type]

    def update(self):
        self.sensor.update()

"""
Support for analog sensors using RPi SPI via MCP 3008.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.rpi_spi_mcp/

Example configuration:

sensor:
  - platform: rpi_spi_mcp
    channels:
      - name: "Humidity Sensor"
        bus: 0
        device: 1
        channel: 0
"""
import logging
import voluptuous as vol
from homeassistant.core import callback
from homeassistant.helpers.event import (async_track_time_interval)
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from spidev import SpiDev

_LOGGER = logging.getLogger(__name__)

CONF_CHANNELS = 'channels'

CHANNEL_SCHEMA = vol.Schema({
    vol.Required('name'): cv.string,
    vol.Required('bus'): cv.positive_int,
    vol.Required('device'): cv.positive_int,
    vol.Required('channel'): cv.positive_int,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_CHANNELS): vol.Schema([CHANNEL_SCHEMA]),

})

def setup_platform(hass, config, add_devices, discovery_info=None):
    channels = config.get(CONF_CHANNELS)
    for channel in channels:
        add_devices([RPiSpiMcpChannel(channel)])

class RPiSpiMcpChannel(Entity):
    def __init__(self, channel):
        self.bus = channel.get('bus')
        self.device = channel.get('device')
        self.channel = channel.get('channel')
        self.spi = SpiDev()
        self._name = channel.get('name')
        self._state = self.get_state()

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    def open(self):
        self.spi.open(self.bus, self.device)

    def close(self):
        self.spi.close()

    def get_state(self):
        self.open()
        adc = self.spi.xfer2([1, (8 + self.channel) << 4, 0])
        data = ((adc[1] & 3) << 8) + adc[2]
        state = round(100 - data / 10.23, 2)
        self.close()
        return state

    def update(self):
        self._state = self.get_state()

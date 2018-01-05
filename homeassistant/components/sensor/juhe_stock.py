"""
Support for monitoring chinese stock market information provided by Juhe.

Stock Market API of Juhe: https://www.juhe.cn/docs/api/id/21

Example configuration.yaml entry
sensor:
  - platform: juhe_stock
    key: xxxxxxxxxxxxxxxxxxxx
    symbols:
      - sz000002
      - sh600600
      - sh600000

key(Required): Key from Stock Market API of Juhe.
symbols(Optional): List of stock market symbols for given companies.
    Default value is sz000002 (万科A).
"""
import logging
import json
import asyncio
from datetime import timedelta

import voluptuous as vol

import http.client

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

ATTR_OPEN = 'open'
ATTR_PREV_CLOSE = 'prev_close'
ATTR_HIGH = 'high'
ATTR_LOW = 'low'
ATTR_NAME = 'friendly_name'

CONF_ATTRIBUTION = "Chinese stock market information provided by Juhe"
CONF_SYMBOLS = 'symbols'
CONF_KEY = 'key'

DEFAULT_SYMBOL = 'sz000002'

ICON = 'mdi:currency-cny'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SYMBOLS, default=[DEFAULT_SYMBOL]):
        vol.All(cv.ensure_list, [cv.string]),
    vol.Required(CONF_KEY): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Aliyun_stock sensor."""

    symbols = config.get(CONF_SYMBOLS)
    key = config.get(CONF_KEY)

    dev = []
    for symbol in symbols:
        data = JuheStockData(hass, symbol, key)
        dev.append(JuheStockSensor(data, symbol))

    async_add_devices(dev, True)


class JuheStockSensor(Entity):
    """Representation of a Juhe Stock sensor."""

    def __init__(self, data, symbol):
        """Initialize the sensor."""
        self.data = data
        self._symbol = symbol
        self._state = None
        self._unit_of_measurement = '元'
        self._name = symbol

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._state is not None:
            return {
                ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
                ATTR_OPEN: self.data.price_open,
                ATTR_PREV_CLOSE: self.data.prev_close,
                ATTR_HIGH: self.data.high,
                ATTR_LOW: self.data.low,
                ATTR_NAME: self.data.name,
            }

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data and updates the states."""
        _LOGGER.debug("Updating sensor %s - %s", self._name, self._state)
        self.data.update()
        self._state = self.data.state


class JuheStockData(object):
    """Get data from Juhe stock imformation."""

    def __init__(self, hass, symbol, key):
        """Initialize the data object."""

        self._symbol = symbol
        self.state = None
        self.price_open = None
        self.prev_close = None
        self.high = None
        self.low = None
        self.name = None
        self.hass = hass

        self.host = 'web.juhe.cn:8080'
        self.url = "/finance/stock/hs?gid=" + self._symbol + "&key=" + key

    def update(self):
        """Get the latest data and updates the states."""
        conn = http.client.HTTPConnection(self.host)
        conn.request("GET", self.url)
        result = conn.getresponse()

        if (result.status != 200):
            _LOGGER.error("Error http reponse: %d", result.status)
            return

        # data = eval(result.read())
        data = json.loads(str(result.read(), encoding='utf-8'))

        if (data['resultcode'] != "200"):
            _LOGGER.error("Error Api return, resultcode=%s, reason=%s",
                          data['resultcode'],
                          data['reason']
                          )
            return

        self.state = data['result'][0]['data']['nowPri']
        self.high = data['result'][0]['data']['todayMax']
        self.low = data['result'][0]['data']['todayMin']
        self.price_open = data['result'][0]['data']['todayStartPri']
        self.prev_close = data['result'][0]['data']['yestodEndPri']
        self.name = data['result'][0]['data']['name']

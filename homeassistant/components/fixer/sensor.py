"""Currency exchange rate support that comes from fixer.io."""
from __future__ import annotations

from datetime import timedelta
import logging

from fixerio import Fixerio
from fixerio.exceptions import FixerioException
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION, CONF_API_KEY, CONF_NAME, CONF_TARGET
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

ATTR_EXCHANGE_RATE = "Exchange rate"
ATTR_TARGET = "Target currency"
ATTRIBUTION = "Data provided by the European Central Bank (ECB)"

DEFAULT_BASE = "USD"
DEFAULT_NAME = "Exchange rate"

ICON = "mdi:currency-usd"

SCAN_INTERVAL = timedelta(days=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_TARGET): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Fixer.io sensor."""
    api_key = config.get(CONF_API_KEY)
    name = config.get(CONF_NAME)
    target = config.get(CONF_TARGET)

    try:
        Fixerio(symbols=[target], access_key=api_key).latest()
    except FixerioException:
        _LOGGER.error("One of the given currencies is not supported")
        return

    data = ExchangeData(target, api_key)
    add_entities([ExchangeRateSensor(data, name, target)], True)


class ExchangeRateSensor(SensorEntity):
    """Representation of a Exchange sensor."""

    def __init__(self, data, name, target):
        """Initialize the sensor."""
        self.data = data
        self._target = target
        self._name = name
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._target

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.data.rate is not None:
            return {
                ATTR_ATTRIBUTION: ATTRIBUTION,
                ATTR_EXCHANGE_RATE: self.data.rate["rates"][self._target],
                ATTR_TARGET: self._target,
            }

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the latest data and updates the states."""
        self.data.update()
        self._state = round(self.data.rate["rates"][self._target], 3)


class ExchangeData:
    """Get the latest data and update the states."""

    def __init__(self, target_currency, api_key):
        """Initialize the data object."""
        self.api_key = api_key
        self.rate = None
        self.target_currency = target_currency
        self.exchange = Fixerio(symbols=[self.target_currency], access_key=self.api_key)

    def update(self):
        """Get the latest data from Fixer.io."""
        self.rate = self.exchange.latest()

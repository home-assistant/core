"""Example integration using DataUpdateCoordinator."""
import logging

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CURRENCY_ICONS, DEFAULT_COIN_ICON, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Bittrex sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    for market in coordinator.data:
        entities.append(Ticker(coordinator, market["symbol"]))

    async_add_entities(entities, True)


class BittrexEntity(CoordinatorEntity):
    """Defines a base Bittrex entity."""

    def __init__(self, coordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return CURRENCY_ICONS.get(self._unit_of_measurement, DEFAULT_COIN_ICON)

    @property
    def device_state_attributes(self):
        """Return additional sensor state attributes."""
        return {
            "symbol": self._data["symbol"],
            "lastTradeRate": self._data["lastTradeRate"],
            "bidRate": self._data["bidRate"],
            "askRate": self._data["askRate"],
            "currency": self._currency,
            "unit_of_measurement": self._unit_of_measurement,
        }


class Ticker(BittrexEntity):
    """Implementation of the ticker sensor."""

    def __init__(self, coordinator, symbol):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.symbol = symbol
        self._data = next(
            item for item in coordinator.data if item["symbol"] == self.symbol
        )
        self._currency = self._data["symbol"].split("-")[0]
        self._unit_of_measurement = self._data["symbol"].split("-")[1]

        self._name = f"Bittrex Ticker - {self._data['symbol']}"
        self._state = self._data["lastTradeRate"]
        self._unique_id = f"bittrex_ticker_{self._data['symbol']})"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique id for the sensor."""
        return self._unique_id

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

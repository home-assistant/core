"""Example integration using DataUpdateCoordinator."""
import logging

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CURRENCY_ICONS, DEFAULT_COIN_ICON, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Bittrex sensors."""
    coordinator = hass.data[DOMAIN]

    entities = []

    for market in coordinator.data:
        entities.append(Ticker(coordinator, market))

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
            "symbol": self.market["symbol"],
            "lastTradeRate": self.market["lastTradeRate"],
            "bidRate": self.market["bidRate"],
            "askRate": self.market["askRate"],
        }


class Ticker(BittrexEntity):
    """Implementation of the ticker sensor."""

    def __init__(self, coordinator, market):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.market = market
        self._currency = self.market["symbol"].split("-")[0]
        self._unit_of_measurement = self.market["symbol"].split("-")[1]

        self._name = f"Bittrex Ticker - {self.market['symbol']}"
        self._state = self.market["lastTradeRate"]
        self._unique_id = f"bittrex_ticker_{self.market['symbol']})"

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

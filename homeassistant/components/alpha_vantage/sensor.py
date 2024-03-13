"""Stock market information from Alpha Vantage."""
from __future__ import annotations

from datetime import timedelta
import logging

from alpha_vantage.foreignexchange import ForeignExchange
from alpha_vantage.timeseries import TimeSeries
import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_API_KEY, CONF_CURRENCY, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

ATTR_CLOSE = "close"
ATTR_HIGH = "high"
ATTR_LOW = "low"

ATTRIBUTION = "Stock market information provided by Alpha Vantage"

CONF_FOREIGN_EXCHANGE = "foreign_exchange"
CONF_FROM = "from"
CONF_SYMBOL = "symbol"
CONF_SYMBOLS = "symbols"
CONF_TO = "to"

ICONS = {
    "BTC": "mdi:currency-btc",
    "EUR": "mdi:currency-eur",
    "GBP": "mdi:currency-gbp",
    "INR": "mdi:currency-inr",
    "RUB": "mdi:currency-rub",
    "TRY": "mdi:currency-try",
    "USD": "mdi:currency-usd",
}

SCAN_INTERVAL = timedelta(minutes=5)

SYMBOL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SYMBOL): cv.string,
        vol.Optional(CONF_CURRENCY): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }
)

CURRENCY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_FROM): cv.string,
        vol.Required(CONF_TO): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_FOREIGN_EXCHANGE): vol.All(cv.ensure_list, [CURRENCY_SCHEMA]),
        vol.Optional(CONF_SYMBOLS): vol.All(cv.ensure_list, [SYMBOL_SCHEMA]),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Alpha Vantage sensor."""
    api_key: str = config[CONF_API_KEY]
    symbols: list[dict[str, str]] = config.get(CONF_SYMBOLS, [])
    conversions: list[dict[str, str]] = config.get(CONF_FOREIGN_EXCHANGE, [])

    if not symbols and not conversions:
        msg = "No symbols or currencies configured."
        persistent_notification.create(hass, msg, "Sensor alpha_vantage")
        _LOGGER.warning(msg)
        return

    timeseries = TimeSeries(key=api_key)

    dev: list[SensorEntity] = []
    for symbol in symbols:
        try:
            _LOGGER.debug("Configuring timeseries for symbols: %s", symbol[CONF_SYMBOL])
            timeseries.get_intraday(symbol[CONF_SYMBOL])
        except ValueError:
            _LOGGER.error("API Key is not valid or symbol '%s' not known", symbol)
        dev.append(AlphaVantageSensor(timeseries, symbol))

    forex = ForeignExchange(key=api_key)
    for conversion in conversions:
        from_cur = conversion.get(CONF_FROM)
        to_cur = conversion.get(CONF_TO)
        try:
            _LOGGER.debug("Configuring forex %s - %s", from_cur, to_cur)
            forex.get_currency_exchange_rate(from_currency=from_cur, to_currency=to_cur)
        except ValueError as error:
            _LOGGER.error(
                "API Key is not valid or currencies '%s'/'%s' not known",
                from_cur,
                to_cur,
            )
            _LOGGER.debug(str(error))
        dev.append(AlphaVantageForeignExchange(forex, conversion))

    add_entities(dev, True)
    _LOGGER.debug("Setup completed")


class AlphaVantageSensor(SensorEntity):
    """Representation of a Alpha Vantage sensor."""

    _attr_attribution = ATTRIBUTION

    def __init__(self, timeseries: TimeSeries, symbol: dict[str, str]) -> None:
        """Initialize the sensor."""
        self._symbol = symbol[CONF_SYMBOL]
        self._attr_name = symbol.get(CONF_NAME, self._symbol)
        self._timeseries = timeseries
        self._attr_native_unit_of_measurement = symbol.get(CONF_CURRENCY, self._symbol)
        self._attr_icon = ICONS.get(symbol.get(CONF_CURRENCY, "USD"))

    def update(self) -> None:
        """Get the latest data and updates the states."""
        _LOGGER.debug("Requesting new data for symbol %s", self._symbol)
        all_values, _ = self._timeseries.get_intraday(self._symbol)
        values = next(iter(all_values.values()))
        if isinstance(values, dict) and "1. open" in values:
            self._attr_native_value = values["1. open"]
        else:
            self._attr_native_value = None
        self._attr_extra_state_attributes = (
            {
                ATTR_CLOSE: values["4. close"],
                ATTR_HIGH: values["2. high"],
                ATTR_LOW: values["3. low"],
            }
            if isinstance(values, dict)
            else {}
        )
        _LOGGER.debug("Received new values for symbol %s", self._symbol)


class AlphaVantageForeignExchange(SensorEntity):
    """Sensor for foreign exchange rates."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self, foreign_exchange: ForeignExchange, config: dict[str, str]
    ) -> None:
        """Initialize the sensor."""
        self._foreign_exchange = foreign_exchange
        self._from_currency = config[CONF_FROM]
        self._to_currency = config[CONF_TO]
        self._attr_name = (
            config.get(CONF_NAME)
            if CONF_NAME in config
            else f"{self._to_currency}/{self._from_currency}"
        )
        self._attr_icon = ICONS.get(self._from_currency, "USD")
        self._attr_native_unit_of_measurement = self._to_currency

    def update(self) -> None:
        """Get the latest data and updates the states."""
        _LOGGER.debug(
            "Requesting new data for forex %s - %s",
            self._from_currency,
            self._to_currency,
        )
        values, _ = self._foreign_exchange.get_currency_exchange_rate(
            from_currency=self._from_currency, to_currency=self._to_currency
        )
        if isinstance(values, dict) and "5. Exchange Rate" in values:
            self._attr_native_value = round(float(values["5. Exchange Rate"]), 4)
        else:
            self._attr_native_value = None
        self._attr_extra_state_attributes = (
            {
                CONF_FROM: self._from_currency,
                CONF_TO: self._to_currency,
            }
            if values is not None
            else {}
        )

        _LOGGER.debug(
            "Received new data for forex %s - %s",
            self._from_currency,
            self._to_currency,
        )

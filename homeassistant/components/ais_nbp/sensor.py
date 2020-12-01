"""ais nbp sensor"""
from datetime import timedelta
import logging

import async_timeout

from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
# Dostosowany do potrzeb i do bycia dobrym użytkownikiem API.
SCAN_INTERVAL = timedelta(minutes=15)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Konfiguracja za pomocą yaml - sposób przestarzały"""
    return


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Konfiguracja za pomcą przepływu konfiguracji."""
    # Aktualnie obowiązująca cena złota
    async_add_entities([AisNbpSensor(hass, "gold", "nbp_gold_price")])
    # Aktualnie obowiązujący kurs średni walut
    _LOGGER.info("Currencies to track: " + str(config_entry.data["currency"]))
    currencies = config_entry.data["currency"]
    for currency in currencies:
        async_add_entities(
            [AisNbpSensor(hass, currency, "nbp_currency_" + currency.lower())]
        )


async def async_unload_entry(hass, entry):
    """Sprzątanie przy usunięciu integracji - tu można dodać kod jeśli potrzeba robić coś więcej"""
    pass


class AisNbpSensor(Entity):
    """Reprezentacja sensora AisHelloSensor."""

    def __init__(self, hass, currency, entity_id):
        """Inicjalizacja sensora."""
        self.hass = hass
        self._currency = currency
        self._entity_id = entity_id
        self._state = None

    @property
    def entity_id(self):
        """Funkcja zwracająca identyfikator sensora."""
        return f"sensor.{self._entity_id}"

    @property
    def name(self):
        """Funkcja zwracająca nazwę sensora."""
        if self._currency.lower() == "gold":
            return "Cena złota"
        elif self._currency.lower() == "eur":
            return "Kurs euro"
        elif self._currency.lower() == "usd":
            return "Kurs dolara"
        elif self._currency.lower() == "chf":
            return "Kurs franka"
        elif self._currency.lower() == "gbp":
            return "Kurs funta"

    @property
    def state(self):
        """Funkcja zwracająca status sensora.
        Wartość sensora powinna zawsze zwracać tylko informacje z pamięci: self._state
        """
        return self._state

    @property
    def unit_of_measurement(self):
        """Funkcja zwracająca jednostkę miary sensora."""
        if self._currency == "gold":
            return "PLN/1g"
        return self._currency

    @property
    def icon(self):
        if self._currency == "gold":
            return "mdi:gold"
        return "mdi:cash-multiple"

    async def async_ask_nbp(self):
        web_session = aiohttp_client.async_get_clientsession(self.hass)
        if self._currency == "gold":
            url = "http://api.nbp.pl/api/cenyzlota?format=json"
        else:
            url = (
                "http://api.nbp.pl/api/exchangerates/rates/a/"
                + self._currency.lower()
                + "?format=json"
            )
        try:
            with async_timeout.timeout(2):
                ws_resp = await web_session.get(url)
                json_info = await ws_resp.json()
                if self._currency == "gold":
                    return json_info[0]["cena"]
                else:
                    return json_info["rates"][0]["mid"]
        except Exception as e:
            _LOGGER.error("Ask NBP error: " + str(e))

    async def async_update(self):
        """Pobranie aktualnego statusu sensora
        aktualizacja wartości powinna odbywać się okresowo, patrz SCAN_INTERVAL = timedelta(minutes=60)
        pytanie serwisu powinno się odbywacć asynchronicznie
        nie powinno się wykonywać częstych blokujących operacji I/O (we/wy) takich jak żądania sieciowe
        """
        _LOGGER.debug("async_update nbp sensor: " + self._currency.lower())
        self._state = await self.async_ask_nbp()

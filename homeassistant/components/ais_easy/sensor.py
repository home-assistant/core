"""ais easy sensor"""
from datetime import timedelta
import json
import logging

import async_timeout

from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
# Dostosowany do potrzeb, pamiętaj by być "dobrym użytkownikiem API".
SCAN_INTERVAL = timedelta(seconds=10)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Konfiguracja za pomocą yaml - sposób przestarzały"""
    return


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Konfiguracja za pomcą przepływu konfiguracji."""
    # Aktualnie obowiązująca cena złota
    async_add_entities(
        [
            AisEasySensor(
                hass,
                config_entry.data["host"],
                config_entry.data["token"],
                "ais_easy_state",
            )
        ]
    )

    # currencies = config_entry.data["currency"]
    # for currency in currencies:
    #     async_add_entities(
    #         [AisEasySensor(hass, currency, "nbp_currency_" + currency.lower())]
    #     )


async def async_unload_entry(hass, entry):
    """Sprzątanie przy usunięciu integracji - tu można dodać kod jeśli potrzeba robić coś więcej"""
    pass


class AisEasySensor(Entity):
    """Reprezentacja sensora AisHelloSensor."""

    def __init__(self, hass, easy_host, easy_token, easy_entity_id):
        """Inicjalizacja sensora."""
        self.hass = hass
        self._host = easy_host
        self._token = easy_token
        self._state = None
        self._status_on_start = True
        self._entity_id = easy_entity_id

    @property
    def entity_id(self):
        """Funkcja zwracająca identyfikator sensora."""
        return f"sensor.{self._entity_id}"

    @property
    def name(self):
        """Funkcja zwracająca nazwę sensora."""
        return "Status PLC"

    @property
    def state(self):
        """Funkcja zwracająca status sensora.
        Wartość sensora powinna zawsze zwracać tylko informacje z pamięci: self._state
        """
        if self._status_on_start:
            self._status_on_start = False
            self.hass.async_add_job(
                self.hass.services.async_call(
                    "homeassistant",
                    "update_entity",
                    {"entity_id": "sensor." + self._entity_id},
                )
            )
        return self._state

    @property
    def unit_of_measurement(self):
        """Funkcja zwracająca jednostkę miary sensora."""
        return "info"

    @property
    def icon(self):
        return "mdi:gold"

    async def async_ask_easy(self):
        web_session = aiohttp_client.async_get_clientsession(self.hass)
        header = {
            "Authorization": "Bearer %s" % self._token,
            "Content-Type": "application/json",
        }
        url = "http://" + self._host + "/api/get/data?elm=STATE"

        try:
            with async_timeout.timeout(15):
                ws_resp = await web_session.get(url, headers=header)
                info = await ws_resp.text()
                info_json = json.loads(info)
                return info_json["SYSINFO"]["STATE"]

        except Exception as e:
            _LOGGER.info("Ask Easy timeout error: " + str(e))

    async def async_update(self):
        """Pobranie aktualnego statusu sensora
        aktualizacja wartości powinna odbywać się okresowo, patrz SCAN_INTERVAL = timedelta(minutes=60)
        pytanie serwisu powinno się odbywacć asynchronicznie
        nie powinno się wykonywać częstych blokujących operacji I/O (we/wy) takich jak żądania sieciowe
        """
        self._state = await self.async_ask_easy()

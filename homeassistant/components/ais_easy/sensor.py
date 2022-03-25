"""ais easy sensor"""
from base64 import b64encode
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
    # PLC EASY
    for x in range(config_entry.data["sensors"]):
        async_add_entities(
            [
                AisEasySensor(
                    hass,
                    config_entry.data["host"],
                    config_entry.data["user"],
                    config_entry.data["pass"],
                    str(x + 1),
                )
            ]
        )


async def async_unload_entry(hass, entry):
    """Sprzątanie przy usunięciu integracji - tu można dodać kod jeśli potrzeba robić coś więcej"""
    pass


class AisEasySensor(Entity):
    """Reprezentacja sensora AisHelloSensor."""

    def __init__(self, hass, easy_host, easy_user, easy_pass, easy_number):
        """Inicjalizacja sensora."""
        self.hass = hass
        self._host = easy_host
        self._user = easy_user
        self._pass = easy_pass
        self._state = None
        self._number = easy_number
        self._unique_id = (
            "ais_easy_" + self._host.replace(".", "") + "_" + str(self._number)
        )

    @property
    def unique_id(self) -> str:
        """Return a unique, friendly identifier for this entity."""
        return f"sensor.{self._unique_id}"

    @property
    def device_info(self):
        """Device info."""
        return {
            "identifiers": {("ais_easy", self._host)},
            "name": f"AIS Easy E4",
            "manufacturer": "Eton",
            "model": "Easy E4",
            "sw_version": "7.32",
            "via_device": None,
        }

    @property
    def name(self):
        """Funkcja zwracająca nazwę sensora."""
        return "Sensor " + self._number

    @property
    def state(self):
        """Funkcja zwracająca status sensora.
        Wartość sensora powinna zawsze zwracać tylko informacje z pamięci: self._state
        """
        return self._state

    @property
    def unit_of_measurement(self):
        """Funkcja zwracająca jednostkę miary sensora."""
        return ""

    @property
    def icon(self):
        return "mdi:eye"

    async def async_ask_easy(self):
        web_session = aiohttp_client.async_get_clientsession(self.hass)
        encoded_credentials = b64encode(
            bytes(f"{self._user}:{self._pass}", encoding="ascii")
        ).decode("ascii")

        header = {
            "Authorization": "Basic %s" % encoded_credentials,
            "Content-Type": "application/json",
        }
        url = "http://" + self._host + "/api/get/data?elm=AI(" + self._number + ")"

        try:
            with async_timeout.timeout(15):
                ws_resp = await web_session.get(url, headers=header)
                info = await ws_resp.text()
                info_json = json.loads(info)
                return info_json["OPERANDS"]["AISINGLE"][0]["V"]

        except Exception as e:
            _LOGGER.error("Ask Easy error: " + str(e))

    async def async_update(self):
        """Pobranie aktualnego statusu sensora
        aktualizacja wartości powinna odbywać się okresowo, patrz SCAN_INTERVAL = timedelta(minutes=60)
        pytanie serwisu powinno się odbywacć asynchronicznie
        nie powinno się wykonywać częstych blokujących operacji I/O (we/wy) takich jak żądania sieciowe
        """
        self._state = await self.async_ask_easy()

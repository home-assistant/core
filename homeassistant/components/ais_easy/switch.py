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
    for x in range(config_entry.data["switches"]):
        async_add_entities(
            [
                AisEasySwitch(
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


class AisEasySwitch(Entity):
    """Reprezentacja sensora AisHelloSensor."""

    def __init__(self, hass, easy_host, easy_user, easy_pass, easy_number):
        """Inicjalizacja sensora."""
        self.hass = hass
        self._host = easy_host
        self._user = easy_user
        self._pass = easy_pass
        self._number = easy_number
        self._state = "off"
        self._unique_id = (
            "switch.ais_easy_" + self._host.replace(".", "") + "_" + str(self._number)
        )
        encoded_credentials = b64encode(
            bytes(f"{self._user}:{self._pass}", encoding="ascii")
        ).decode("ascii")
        self._header = {
            "Authorization": "Basic %s" % encoded_credentials,
            "Content-Type": "application/json",
        }

    @property
    def unique_id(self) -> str:
        """Return a unique, friendly identifier for this entity."""
        return f"{self._unique_id}"

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
        return "Switch " + str(self._number)

    @property
    def state(self):
        """Funkcja zwracająca status przełącznika.
        Wartość sensora powinna zawsze zwracać tylko informacje z pamięci: self._state
        """
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self._state = "on"
        url = (
            "http://" + self._host + "/api/set/op?op=M&index=" + self._number + "&val=1"
        )
        await self.async_run_easy(url)

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self._state = "off"
        url = (
            "http://" + self._host + "/api/set/op?op=M&index=" + self._number + "&val=0"
        )
        await self.async_run_easy(url)

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        if self._state == "on":
            self._state = "off"
            url = (
                "http://"
                + self._host
                + "/api/set/op?op=M&index="
                + self._number
                + "&val=0"
            )
        else:
            self._state = "on"
            url = (
                "http://"
                + self._host
                + "/api/set/op?op=M&index="
                + self._number
                + "&val=1"
            )
        await self.async_run_easy(url)

    async def async_run_easy(self, url):
        web_session = aiohttp_client.async_get_clientsession(self.hass)
        try:
            with async_timeout.timeout(15):
                ws_resp = await web_session.get(url, headers=self._header)
                info = await ws_resp.text()
                _LOGGER.info("Ask Easy info: " + str(info))

        except Exception as e:
            _LOGGER.error("Ask Easy error: " + str(e))

        web_session = aiohttp_client.async_get_clientsession(self.hass)
        try:
            with async_timeout.timeout(15):
                url = (
                    "http://" + self._host + "/api/get/data?elm=O(" + self._number + ")"
                )
                ws_resp = await web_session.get(url, headers=self._header)
                info = await ws_resp.text()
                json_text = json.loads(info)
                val = json_text["OPERANDS"]["OSINGLE"][0]["V"]
                if val == 1:
                    self._state = "on"
                else:
                    self._state = "off"
        except Exception as e:
            _LOGGER.error("Ask Easy error: " + str(e))

    async def async_update(self):
        """Pobranie aktualnego statusu
        aktualizacja wartości powinna odbywać się okresowo, patrz SCAN_INTERVAL = timedelta(minutes=60)
        pytanie serwisu powinno się odbywacć asynchronicznie
        nie powinno się wykonywać częstych blokujących operacji I/O (we/wy) takich jak żądania sieciowe
        """
        web_session = aiohttp_client.async_get_clientsession(self.hass)
        try:
            with async_timeout.timeout(15):
                url = (
                    "http://" + self._host + "/api/get/data?elm=O(" + self._number + ")"
                )
                ws_resp = await web_session.get(url, headers=self._header)
                info = await ws_resp.text()
                json_text = json.loads(info)
                _LOGGER.debug("Ask Easy info: " + str(json_text))
                val = json_text["OPERANDS"]["OSINGLE"][0]["V"]
                _LOGGER.debug("Ask Easy val: " + str(val))
                if val == 1:
                    self._state = "on"
                else:
                    self._state = "off"
        except Exception as e:
            _LOGGER.error("Ask Easy error: " + str(e))

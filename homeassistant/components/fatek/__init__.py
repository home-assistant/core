"""The Fatek integration."""
from __future__ import annotations

from abc import abstractmethod
from datetime import timedelta
import json
import logging
import urllib.request

from bitarray import bitarray

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

# from .light import FatekLight

PLATFORMS: list[Platform] = [Platform.LIGHT]
LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Utworzenie integracji."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fatek from a config entry."""
    # LOGGER.error("Fatek: async_setup_entry: %s", entry.entry_id)
    fatek_config = FatekServerConfig("10.166.5.245")
    coordinator = FatekStateCoordinator(hass, fatek_config)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["entry_id"] = entry.entry_id
    hass.data[DOMAIN]["coordinator_running"] = False
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await coordinator.async_config_entry_first_refresh()
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_config_entry_update_listener))
    return True


async def async_config_entry_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class FatekServerConfig:
    """Parametry FatekServer'a."""

    def __init__(self, fatek_server_ip: str) -> None:
        """Utworzenei klasy serwera Fateka."""
        self.name = "Fatek.Server"
        self._fatek_server_ip: str = fatek_server_ip


class FatekStateCoordinator(DataUpdateCoordinator[None]):
    """Klasa do komuniakcji / aktualizacji danych z FATEK'a."""

    def __init__(self, hass, fatek_server_config: FatekServerConfig) -> None:
        """Utworzenie koordnatora."""
        self._fatek_server_config: FatekServerConfig = fatek_server_config
        self._m_entities: dict[int, FatekEntity] = {}
        self._m_register = bitarray(2001)
        self._m_register.setall(0)

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=5),
            request_refresh_debouncer=Debouncer(
                hass, LOGGER, cooldown=2.0, immediate=False
            ),
        )

    @property
    def fatek_server_config(self) -> FatekServerConfig:
        """Return the system descriptor."""
        return self._fatek_server_config

    @property
    def unique_id(self) -> str:
        """Return the system descriptor."""
        entry: ConfigEntry | None = self.config_entry
        assert entry
        if entry.unique_id:
            return entry.unique_id
        assert entry.entry_id
        return entry.entry_id

    def add_m_entity(self, entity) -> bool:
        """Dodaje encję do tablicy."""
        self._m_entities[entity.index] = entity
        return True

    def get_m_register(self, index) -> bool:
        """Zwraca wartość rejestru M dla podanego indeksu."""
        return self._m_register[index]

    def get_m_registers(self, start, count) -> bool:
        """Pobranie rejestrów M."""
        reg_id = f"M_{start}_{count}"
        str_url = f"http://10.166.5.245:13001/fatek_get?q={reg_id}"
        # http://myhome.marcinziarko.com:13001/fatek_get?q=set
        # LOGGER.info("Info. Fatek: FatekStateCoordinator: get_m_registers: %s", str_url)
        with urllib.request.urlopen(str_url) as url:
            data = json.load(url)
            states = data[0][reg_id]
            # LOGGER.info("Fatek states: %s", states)
            i: int = 0
            j: int
            index: int = start
            while i < count:
                j = i * 2
                val = states[j : j + 1]
                if val == "0":
                    if self._m_register[index] == 1:
                        self.toogle_m_state(index)
                else:
                    if self._m_register[index] == 0:
                        self.toogle_m_state(index)
                i += 1
                index += 1
        return True

    def toogle_m_state(self, index) -> bool:
        """Zmiana stanu rejestru M."""
        LOGGER.info("Fatek: FatekStateCoordinator: toogle_m_state: %s", index)
        self._m_register[index] = not self._m_register[index]
        if index in self._m_entities:
            self._m_entities[index].set_entity_state(self._m_register[index])
        return True

    def set_m_register(self, index: int, value: bool) -> bool:
        """Ustawienie rejestrów M."""
        if value is True:
            reg_id = f"M_{index}_1"
            self._m_register[index] = 1
        else:
            reg_id = f"M_{index}_0"
            self._m_register[index] = 0
        str_url = f"http://10.166.5.245:13002/fatek_set?q={reg_id}"
        # LOGGER.info(str_url)
        with urllib.request.urlopen(str_url) as url:
            data = json.load(url)
            LOGGER.info(data)
        return True

    @callback
    async def _async_update_data(self):
        """Pobieranie danych z FatekServera."""
        # LOGGER.info("FatekStateCoordinator: _async_update_data")
        await self.hass.async_add_executor_job(self.get_m_registers, 875, 15)


class FatekServer(CoordinatorEntity):
    """Klasa do odpytanwiania Fatek Server'a."""

    coordinator: FatekStateCoordinator

    def __init__(self, coordinator: FatekStateCoordinator, entry_id: str) -> None:
        """Utowrzenie encji do pobierania danych z Fateka Server'a."""
        LOGGER.error("FatekServer: init: ")
        self.entity_id: str = "fatek.fatek_server_coordinator"
        self._uid: str = "fatek_coordinator_" + entry_id
        self._name: str = "Fatek Server Coordinator"
        self._friendly_name: str = "Fatek Server Coordinator"
        super().__init__(coordinator)

    @property
    def unique_id(self) -> str:
        """Unikalany identyfikator encji."""
        return self._uid

    @property
    def available(self) -> bool:
        """Znacznik czy encja jest dostępna."""
        return False

    @property
    def entity_registry_visible_default(self) -> bool:
        """Znacznik czy encja ma być widoczna."""
        return False

    #    @property
    #    def entity_id(self: FatekServer) -> str:
    #        """Identyfikator encji."""
    #        return self._entity_id
    #
    #    @entity_id.setter
    #    def entity_id(self: FatekServer, value: Any) -> None:
    #        """Ustawienie entity_id."""
    #        # LOGGER.error("Setting entity id to: %s",self._entity_id,)
    #        # self._entity_id = value

    @property
    def name(self) -> str:
        """Nazwa ."""
        return self._name

    @property
    def friendly_name(self) -> str:
        """Przyjazna nazwa."""
        return self._friendly_name


class FatekEntity(Entity):
    """Encje Fateka."""

    def __init__(
        self,
        coordinator: FatekStateCoordinator,
        name: str,
        register: str,
        index: int,
    ) -> None:
        """Initialize klasy FatekEntity."""
        LOGGER.info("Initializing FatekEntity: %s_%s ", register, index)
        self._name: str = name
        self._register: str = register.upper()
        self._index: int = index
        self._friendly_name: str = name
        self._available: bool = True

        self.entity_id: str = "light.fatek_" + register.lower() + str(index)
        self._coordinator: FatekStateCoordinator = coordinator

        if self._register == "M":
            coordinator.add_m_entity(self)

    @property
    def register(self) -> str:
        """Nazwa rejestru."""
        return self._register

    @property
    def index(self) -> int:
        """Rejestr."""
        return self._index

    @property
    def unique_id(self) -> str:
        """Unikalne identyfikator encji."""
        return self._register + str(self._index)

    #    @property
    #    def entity_id(self) -> str:
    #        """Identyfikator encji."""
    #        return self._entity_id
    #
    #    @entity_id.setter
    #    def entity_id(self: FatekEntity, value: Any) -> None:
    #        """Ustawienie entity_id."""
    #        # LOGGER.error("Setting entity id to: %s",self._entity_id,)
    #        # self._entity_id = value
    #
    @property
    def name(self) -> str:
        """Nazwa światła."""
        # LOGGER.error("Fatek: FatekLight: name %s", self._name)
        return self._name

    @property
    def friendly_name(self) -> str:
        """Przyjazna nazwa."""
        # LOGGER.error("Fatek: FatekLight: friendly_name")
        return self._friendly_name

    @property
    def available(self) -> bool:
        """Czy encja jest dostępna?."""
        return self._available

    @abstractmethod
    def set_entity_state(self, new_state):
        """Metoda abstrakcyjna ustawienia stanu logicznego."""

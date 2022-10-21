"""Platform for light integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.light import PLATFORM_SCHEMA, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import FatekEntity, FatekServer, FatekStateCoordinator
from .const import DOMAIN, FATEK_INDEX, FATEK_REGISTER

LOGGER = logging.getLogger("Fatek")

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(FATEK_REGISTER, default="M"): str,
        vol.Required(FATEK_INDEX, default=0): int,
        vol.Required(CONF_NAME, default=""): str,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Perform the setup for FatekLight devices."""
    name = config[CONF_NAME]
    register = config[FATEK_REGISTER]
    index = config[FATEK_INDEX]
    entry_id: str = hass.data[DOMAIN]["entry_id"]
    if len(entry_id) == 32:
        coordinator: FatekStateCoordinator = hass.data[DOMAIN][entry_id]
        add_entities([FatekLight(coordinator, name, register, index)], True)


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Utworzenie encji."""
    if hass.data[DOMAIN]["coordinator_running"] is False:
        hass.data[DOMAIN]["coordinator_running"] = True
        entry_id = config.entry_id
        coordinator: FatekStateCoordinator = hass.data[DOMAIN][entry_id]
        async_add_entities([FatekServer(coordinator, entry_id)])


class FatekLight(LightEntity, FatekEntity):
    """Światło sterowane przez Fateka."""

    def __init__(
        self,
        coordinator: FatekStateCoordinator,
        name: str,
        register: str,
        index: int,
    ) -> None:
        """Initialize the FatekLight."""
        LOGGER.info("Initializing Fatek.Light: %s_%s ", register, index)
        #        super().__init__()
        LightEntity.__init__(self)
        FatekEntity.__init__(self, coordinator, name, register, index)
        self._state: bool = False

    def set_entity_state(self, new_state) -> bool:
        """Ustawienie stanu."""
        # LOGGER.info("FatekLight: set_state: %s", self.entity_id)
        if self.hass.states.get(self.entity_id):
            if new_state == 1:
                self.hass.states.async_set(self.entity_id, "on")
            else:
                self.hass.states.async_set(self.entity_id, "off")
        return True

    def update(self) -> None:
        """Synchroniuzj stan."""
        # LOGGER.info("FatekLight: update: %s ", self.entity_id)
        b_new_state = self._coordinator.get_m_register(self._index)
        # LOGGER.info(b_new_state)
        if b_new_state != self._state:
            new_state = "off"
            if b_new_state:
                new_state = "on"
            # LOGGER.info("Fatek: Zmiana stanu %s na: %s", self._entity_id, new_state)
            if self.hass.states.get(self.entity_id):
                self.hass.states.async_set(self.entity_id, new_state)

    @property
    def is_on(self) -> bool:
        """Czy światło jest włączone?."""
        # LOGGER.info("FatekLight: is_on: %s ", self.entity_id)
        self._state = self._coordinator.get_m_register(self._index)
        return self._state

    def turn_on(self, **kwargs: Any) -> None:
        """Włącz światło."""
        self._coordinator.set_m_register(self._index, True)
        # LOGGER.info("FatekLight: turn_on: OK")
        self._state = True

    def turn_off(self, **kwargs: Any) -> None:
        """Wyłącz światło."""
        self._coordinator.set_m_register(self._index, False)
        # LOGGER.info("FatekLight: turn_off: OK")
        self._state = False

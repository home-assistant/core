""" definition of all services for this integration """
import asyncio
import logging

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.typing import HomeAssistantType

from ..pyextalife import ExtaLifeAPI
from .const import DOMAIN
from .typing import CoreType

# services
SVC_RESTART = "restart"  # restart controller

_LOGGER = logging.getLogger(__name__)

SCHEMA_BASE = vol.Schema({vol.Required(CONF_ENTITY_ID): cv.entity_id})
SCHEMA_RESTART = SCHEMA_TEST_BUTTON = SCHEMA_BASE
SCHEMA_TEST_BUTTON = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required("button"): str,
        vol.Required("channel_id"): str,
        vol.Required("event"): str,
    }
)


class ExtaLifeServices:
    """ handle Exta Life services """

    def __init__(self, hass: HomeAssistantType):
        self._hass = hass
        self._services = []

    def _get_core(self, entity_id: str) -> CoreType:
        """ Resolve the Core helper class """
        from .core import Core

        return Core.get(self._get_entry_id(entity_id))

    def _get_entry_id(self, entity_id: str):
        """ Resolve ConfigEntry.entry_id for entity_id """
        registry = asyncio.run_coroutine_threadsafe(
            er.async_get_registry(self._hass), self._hass.loop
        ).result()
        return registry.async_get(entity_id).config_entry_id

    async def async_register_services(self):
        """ register all Exta Life integration services """
        self._hass.services.async_register(
            DOMAIN, SVC_RESTART, self._handle_restart, SCHEMA_RESTART
        )
        self._services.append(SVC_RESTART)
        self._hass.services.async_register(
            DOMAIN, "test_button", self._handle_test_button, SCHEMA_TEST_BUTTON
        )
        self._services.append("test_button")

    async def async_unregister_services(self):
        """ Unregister all Exta Life integration services """
        for service in self._services:
            self._hass.services.async_remove(DOMAIN, service)

    def _handle_restart(self, call):
        """ service: extalife.restart """
        entity_id = call.data.get(CONF_ENTITY_ID)

        core = self._get_core(entity_id)
        core.api.restart()

    def _handle_test_button(self, call):
        from .common import PseudoPlatform
        from .core import Core

        button = call.data.get("button")
        entity_id = call.data.get(CONF_ENTITY_ID)
        channel_id = call.data.get("channel_id")
        event = call.data.get("event")

        data = {"button": button}
        core = self._get_core(entity_id)
        entry_id = None

        signal = PseudoPlatform.get_notif_upd_signal(channel_id)

        num = 0

        def click():
            nonlocal num
            seq = 1
            num += 1
            data = {"button": button, "click": num, "sequence": seq}
            data["state"] = 1
            core.async_signal_send_sync(signal, data)

            data = data.copy()
            seq += 1
            data["state"] = 0
            data["sequence"] = seq

            core.async_signal_send_sync(signal, data)

        if event == "triple":
            click()
            click()
            click()

        elif event == "double":
            click()
            click()

        elif event == "single":
            click()

        elif event == "down":
            data["state"] = 1
            core.async_signal_send_sync(signal, data)

        elif event == "up":
            data["state"] = 0
            core.async_signal_send_sync(signal, data)

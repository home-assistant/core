"""Support for setting the level of logging for components."""
from __future__ import annotations

import logging
import os
from queue import SimpleQueue

import voluptuous as vol

from homeassistant.const import CONF_FILENAME, EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ATTRIBUTES,
    DEFAULT_FILENAME,
    DOMAIN,
    LOGATTRS,
    LOGGER,
    SERVICE_ROTATE,
    LogAttribute,
)
from .helpers import setup_listener_handler, setup_queue_handler

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_ATTRIBUTES, default=LOGATTRS): vol.All(
                    cv.ensure_list, [vol.In(LOGATTRS)]
                ),
                vol.Optional(CONF_FILENAME, default=DEFAULT_FILENAME): cv.path,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the jsonlog component."""

    logpath: str = config[DOMAIN][CONF_FILENAME]
    if not os.path.isabs(logpath):
        logpath = hass.config.path(logpath)
    logattrs = [LogAttribute(attr) for attr in config[DOMAIN][CONF_ATTRIBUTES]]

    LOGGER.info("Setting up JSON log at %s", logpath)
    if not (listener_handler := setup_listener_handler(logpath=logpath)):
        return False

    queue: SimpleQueue[logging.Handler] = SimpleQueue()
    queue_handler = setup_queue_handler(queue=queue, logattrs=logattrs)
    hass.data[DOMAIN] = queue_handler

    @callback
    def _async_stop_handler(event: Event) -> None:
        """Cleanup handler."""
        queue_handler.close()
        logging.root.removeHandler(queue_handler)
        del hass.data[DOMAIN]

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_stop_handler)

    logging.root.addHandler(queue_handler)
    listener = logging.handlers.QueueListener(queue, listener_handler)
    queue_handler.listener = listener
    listener.start()

    async def async_service_handler_rotate(service: ServiceCall) -> None:
        """Handle log file rotation service call."""
        try:
            assert listener_handler
            listener_handler.doRollover()
            LOGGER.info("Rotated log file")
        except OSError as err:
            LOGGER.error("Error rotating log file: %s", err)

    hass.services.async_register(DOMAIN, SERVICE_ROTATE, async_service_handler_rotate)

    return True

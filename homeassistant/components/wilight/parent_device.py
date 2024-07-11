"""The WiLight Device integration."""

from __future__ import annotations

import asyncio
import logging

import pywilight
from pywilight.wilight_device import PyWiLightDevice
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

_LOGGER = logging.getLogger(__name__)


class WiLightParent:
    """Manages a single WiLight Parent Device."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the system."""
        self._host: str = config_entry.data[CONF_HOST]
        self._hass = hass
        self._api: PyWiLightDevice | None = None

    @property
    def host(self) -> str:
        """Return the host of this parent."""
        return self._host

    @property
    def api(self) -> PyWiLightDevice | None:
        """Return the api of this parent."""
        return self._api

    async def async_setup(self) -> bool:
        """Set up a WiLight Parent Device based on host parameter."""
        host = self._host
        hass = self._hass

        api_device = await hass.async_add_executor_job(create_api_device, host)

        if api_device is None:
            return False

        @callback
        def disconnected() -> None:
            # Schedule reconnect after connection has been lost.
            _LOGGER.warning("WiLight %s disconnected", api_device.device_id)
            async_dispatcher_send(
                hass, f"wilight_device_available_{api_device.device_id}", False
            )

        @callback
        def reconnected() -> None:
            # Schedule reconnect after connection has been lost.
            _LOGGER.warning("WiLight %s reconnect", api_device.device_id)
            async_dispatcher_send(
                hass, f"wilight_device_available_{api_device.device_id}", True
            )

        async def connect(api_device: PyWiLightDevice) -> None:
            # Set up connection and hook it into HA for reconnect/shutdown.
            _LOGGER.debug("Initiating connection to %s", api_device.device_id)

            client = await api_device.config_client(
                disconnect_callback=disconnected,
                reconnect_callback=reconnected,
                loop=asyncio.get_running_loop(),
                logger=_LOGGER,
            )

            # handle shutdown of WiLight asyncio transport
            hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, lambda x: client.stop()
            )

            _LOGGER.info("Connected to WiLight device: %s", api_device.device_id)

        await connect(api_device)

        self._api = api_device

        return True

    async def async_reset(self) -> None:
        """Reset api."""

        # If the initialization was not wrong.
        if self._api is not None:
            self._api.client.stop()


def create_api_device(host: str) -> PyWiLightDevice:
    """Create an API Device."""
    try:
        return pywilight.device_from_host(host)
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
    ) as err:
        _LOGGER.error("Unable to access WiLight at %s (%s)", host, err)
        return None

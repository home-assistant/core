"""Code to set up all communications with Crownstones."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from crownstone_cloud import CrownstoneCloud
from crownstone_cloud.exceptions import (
    CrownstoneAuthenticationError,
    CrownstoneUnknownError,
)
from crownstone_sse import CrownstoneSSEAsync
from crownstone_uart import CrownstoneUart, UartEventBus
from crownstone_uart.Exceptions import UartException

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client

from .const import (
    ATTR_UART,
    CONF_USB_PATH,
    CONF_USB_SPHERE,
    DOMAIN,
    PLATFORMS,
    SSE_LISTENERS,
    UART_LISTENERS,
)
from .helpers import get_port
from .listeners import setup_sse_listeners, setup_uart_listeners

_LOGGER = logging.getLogger(__name__)


class CrownstoneEntryManager:
    """Manage a Crownstone config entry."""

    uart: CrownstoneUart
    cloud: CrownstoneCloud
    sse: CrownstoneSSEAsync

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the hub."""
        self.hass = hass
        self.config_entry = config_entry
        self.listeners: dict[str, Any] = {}
        self.usb_sphere_id: str | None = None

    async def async_setup(self) -> bool:
        """
        Set up a Crownstone config entry.

        This class is a combination of Crownstone cloud, Crownstone SSE and Crownstone uart.
        Returns True if the setup was successful.
        """
        email = self.config_entry.data[CONF_EMAIL]
        password = self.config_entry.data[CONF_PASSWORD]

        self.cloud = CrownstoneCloud(
            email=email,
            password=password,
            clientsession=aiohttp_client.async_get_clientsession(self.hass),
        )
        # Login & sync all user data
        try:
            await self.cloud.async_initialize()
        except CrownstoneAuthenticationError as auth_err:
            _LOGGER.error(
                "Auth error during login with type: %s and message: %s",
                auth_err.type,
                auth_err.message,
            )
            return False
        except CrownstoneUnknownError as unknown_err:
            _LOGGER.error("Unknown error during login")
            raise ConfigEntryNotReady from unknown_err

        # A new clientsession is created because the default one does not cleanup on unload
        self.sse = CrownstoneSSEAsync(
            email=email,
            password=password,
            access_token=self.cloud.access_token,
            websession=aiohttp_client.async_create_clientsession(self.hass),
        )
        # Listen for events in the background, without task tracking
        asyncio.create_task(self.async_process_events(self.sse))
        setup_sse_listeners(self)

        # Set up a Crownstone USB only if path exists
        if self.config_entry.data[CONF_USB_PATH] is not None:
            await self.async_setup_usb()

        # Save the sphere where the USB is located
        # Makes HA aware of the Crownstone environment HA is placed in, a user can have multiple
        self.usb_sphere_id = self.config_entry.data[CONF_USB_SPHERE]

        self.hass.data.setdefault(DOMAIN, {})[self.config_entry.entry_id] = self
        self.hass.config_entries.async_setup_platforms(self.config_entry, PLATFORMS)

        # HA specific listeners
        self.config_entry.async_on_unload(
            self.config_entry.add_update_listener(_async_update_listener)
        )
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.on_shutdown)

        return True

    async def async_process_events(self, sse_client: CrownstoneSSEAsync) -> None:
        """Asynchronous iteration of Crownstone SSE events."""
        async with sse_client as client:
            async for event in client:
                if event is not None:
                    # Make SSE updates, like ability change, available to the user
                    self.hass.bus.async_fire(f"{DOMAIN}_{event.type}", event.data)

    async def async_setup_usb(self) -> None:
        """Attempt setup of a Crownstone usb dongle."""
        # Trace by-id symlink back to the serial port
        serial_port = await self.hass.async_add_executor_job(
            get_port, self.config_entry.data[CONF_USB_PATH]
        )
        if serial_port is None:
            return

        self.uart = CrownstoneUart()
        # UartException is raised when serial controller fails to open
        try:
            await self.uart.initialize_usb(serial_port)
        except UartException:
            delattr(self, ATTR_UART)
            # Set entry data for usb to null
            updated_entry_data = self.config_entry.data.copy()
            updated_entry_data[CONF_USB_PATH] = None
            updated_entry_data[CONF_USB_SPHERE] = None
            # Ensure that the user can configure an USB again from options
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=updated_entry_data, options={}
            )
            # Show notification to ensure the user knows the cloud is now used
            persistent_notification.async_create(
                self.hass,
                f"Setup of Crownstone USB dongle was unsuccessful on port {serial_port}.\n \
                Crownstone Cloud will be used to switch Crownstones.\n \
                Please check if your port is correct and set up the USB again from integration options.",
                "Crownstone",
                "crownstone_usb_dongle_setup",
            )
            return

        setup_uart_listeners(self)

    async def async_unload(self) -> bool:
        """Unload the current config entry."""
        # Authentication failed
        if self.cloud.cloud_data is None:
            return True

        self.sse.close_client()
        for sse_unsub in self.listeners[SSE_LISTENERS]:
            sse_unsub()

        if hasattr(self, ATTR_UART):
            self.uart.stop()
            for subscription_id in self.listeners[UART_LISTENERS]:
                UartEventBus.unsubscribe(subscription_id)

        unload_ok = await self.hass.config_entries.async_unload_platforms(
            self.config_entry, PLATFORMS
        )

        if unload_ok:
            self.hass.data[DOMAIN].pop(self.config_entry.entry_id)

        return unload_ok

    @callback
    def on_shutdown(self, _: Event) -> None:
        """Close all IO connections."""
        self.sse.close_client()
        if hasattr(self, ATTR_UART):
            self.uart.stop()


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)

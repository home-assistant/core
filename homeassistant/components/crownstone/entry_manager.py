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
from homeassistant.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_UNIQUE_ID,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client

from .const import (
    ATTR_UART,
    CONF_USB_PATH,
    CONF_USE_CROWNSTONE_USB,
    CROWNSTONE_USB,
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
        # Setup email and password gained from config flow
        customer_email = self.config_entry.data[CONF_EMAIL]
        customer_password = self.config_entry.data[CONF_PASSWORD]

        # Add entry update listener
        self.config_entry.async_on_unload(
            self.config_entry.add_update_listener(async_update_entry_options)
        )

        # Create cloud instance
        self.cloud = CrownstoneCloud(
            email=customer_email,
            password=customer_password,
            clientsession=aiohttp_client.async_get_clientsession(self.hass),
        )
        # Login
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

        # Create SSE instance
        # a new clientsession is created because the default one does not cleanup on unload
        self.sse = CrownstoneSSEAsync(
            email=customer_email,
            password=customer_password,
            access_token=self.cloud.access_token,
            websession=aiohttp_client.async_create_clientsession(self.hass),
        )
        # Listen for events in the background, without task tracking
        asyncio.create_task(self.async_process_events(self.sse))
        # Create listeners for events to update entity data
        setup_sse_listeners(self)

        # Check if a usb by-id exists, if not use cloud
        if self.config_entry.data[CONF_USB_PATH] is not None:
            port = await self.hass.async_add_executor_job(
                get_port, self.config_entry.data[CONF_USB_PATH]
            )
            # port can be None when Home Assistant is started without the USB plugged in
            if port is not None:
                self.uart = CrownstoneUart()
                # UartException is raised when serial controller fails to open
                try:
                    await self.uart.initialize_usb(port)
                except UartException:
                    delattr(self, ATTR_UART)
                    # remove usb path to make usb setup available from options
                    entry_data = self.config_entry.data.copy()
                    entry_data[CONF_USB_PATH] = None
                    self.hass.config_entries.async_update_entry(
                        entry=self.config_entry, data=entry_data
                    )
                    # show notification to ensure the user knows the cloud is now used
                    persistent_notification.async_create(
                        self.hass,
                        f"Setup of Crownstone USB dongle was unsuccessful on port {port}.\n \
                        Crownstone Cloud will be used to switch Crownstones.\n \
                        Please check if your port is correct and set up the USB again from integration options.",
                        "Crownstone",
                        "crownstone_usb_dongle_setup",
                    )
                # Create listeners for uart events
                setup_uart_listeners(self)

        # Save in what sphere the Crownstone USB is if it was setup correctly
        # Crownstones could only be switched using the USB if they are in the same sphere (using BLE)
        # Assuming that the other spheres are different buildings
        if hasattr(self, ATTR_UART):
            for sphere in self.cloud.cloud_data:
                for crownstone in sphere.crownstones:
                    if crownstone.type == CROWNSTONE_USB:
                        self.usb_sphere_id = sphere.cloud_id

        # create listener for when home assistant is stopped
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.on_shutdown)

        # register all entities
        self.hass.config_entries.async_setup_platforms(self.config_entry, PLATFORMS)

        return True

    async def async_process_events(self, sse_client: CrownstoneSSEAsync) -> None:
        """Asynchronous iteration of Crownstone SSE events."""
        async with sse_client as client:
            async for event in client:
                if event is not None:
                    # make SSE updates, like ability change, available to the user
                    self.hass.bus.async_fire(f"{DOMAIN}_{event.type}", event.data)

    async def async_unload(self) -> bool:
        """Unload the current config entry."""
        # authentication failed
        if self.cloud.cloud_data is None:
            return True

        # close sse client and unsub from listeners
        self.sse.close_client()
        for sse_unsub in self.listeners[SSE_LISTENERS]:
            sse_unsub()

        # close uart connection and unsub from listeners
        if hasattr(self, ATTR_UART):
            self.uart.stop()
            for subscription_id in self.listeners[UART_LISTENERS]:
                UartEventBus.unsubscribe(subscription_id)

        # unload all platform entities
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


async def async_update_entry_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    entry_data = entry.data.copy()
    # USB was configured at setup & user wants to remove config
    if (
        not entry.options.get(CONF_USE_CROWNSTONE_USB)
        and entry.data.get(CONF_USB_PATH) is not None
    ):
        entry_data[CONF_USB_PATH] = None

        # update and reload
        # USB connection is closed and entry will be created without USB connection
        hass.config_entries.async_update_entry(entry, data=entry_data)
        await hass.config_entries.async_reload(entry.entry_id)

    # USB was not configured at setup & user wants to configure
    # Init config flow on USB configuration step
    elif (
        entry.options.get(CONF_USE_CROWNSTONE_USB)
        and entry.data.get(CONF_USB_PATH) is None
    ):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "usb_config"},
                data={CONF_UNIQUE_ID: entry.entry_id},
            )
        )

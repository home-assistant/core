"""Code to set up all communications with Crownstones."""
from __future__ import annotations

import asyncio
from functools import partial
import logging
from typing import Any, cast

from crownstone_cloud import CrownstoneCloud
from crownstone_cloud.exceptions import (
    CrownstoneAuthenticationError,
    CrownstoneUnknownError,
)
from crownstone_sse import CrownstoneSSEAsync
from crownstone_uart import CrownstoneUart, UartEventBus

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
    CONF_USB_PATH,
    CONF_USE_CROWNSTONE_USB,
    DOMAIN,
    LIGHT_PLATFORM,
    SSE,
    UART,
)
from .helpers import get_port
from .listeners import create_data_listeners

_LOGGER = logging.getLogger(__name__)


class CrownstoneEntryManager:
    """Manage a Crownstone config entry."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the hub."""
        self.hass = hass
        self.config_entry = config_entry
        self.uart = cast(CrownstoneUart, None)
        self.cloud = cast(CrownstoneCloud, None)
        self.sse = cast(CrownstoneSSEAsync, None)
        self.listeners: dict[str, Any] = {}

    async def async_setup(self) -> bool:
        """
        Set up a Crownstone config entry.

        This class is a combination of Crownstone cloud, Crownstone SSE and Crownstone uart.
        Returns True if the setup was successful.
        """
        # Setup email and password gained from config flow
        customer_email = self.config_entry.data[CONF_EMAIL]
        customer_password = self.config_entry.data[CONF_PASSWORD]

        # Add entry listener
        self.config_entry.async_on_unload(
            self.config_entry.add_update_listener(options_update_listener)
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
        asyncio.create_task(self.process_events(self.sse))

        # Check if a usb by-id exists, if not use cloud
        if self.config_entry.data[CONF_USB_PATH] is not None:
            port = await self.hass.async_add_executor_job(
                partial(get_port, self.config_entry.data[CONF_USB_PATH])
            )
            # port is None when Home Assistant is started without the USB plugged in,
            # but a setup exists
            if port is not None:
                self.uart = CrownstoneUart()
                # initialize USB, this waits for the usb to be initialized
                # this usually takes less than a second, so cancel if it's taking too long
                try:
                    await asyncio.wait_for(
                        self.uart.initialize_usb(f"/dev/{port}"), timeout=5
                    )
                except asyncio.TimeoutError:
                    _LOGGER.warning(
                        "Crownstone USB dongle failed to initialize on port /dev/%s",
                        port,
                    )

        # Create listeners for SSE and UART
        create_data_listeners(self.hass, self)

        # create listener for when home assistant is stopped
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.on_close)

        # register crownstone entities
        self.hass.async_create_task(
            self.hass.config_entries.async_forward_entry_setup(
                self.config_entry, LIGHT_PLATFORM
            )
        )

        return True

    async def process_events(self, sse_client: CrownstoneSSEAsync) -> None:
        """Asynchronous iteration of Crownstone SSE events."""
        async with sse_client as client:
            async for event in client:
                if event is not None:
                    # make SSE updates, like ability change, available to the user
                    self.hass.bus.async_fire(f"{DOMAIN}_{event.type}", event.data)

    async def async_unload(self) -> bool:
        """Unload the current config entry."""
        # stop services
        if self.uart is not None:
            self.uart.stop()
        if self.sse is not None:
            self.sse.close_client()

        # authentication failed
        if self.cloud.cloud_data is None:
            return True

        # Unsubscribe from listeners
        for sse_unsub in self.listeners[SSE]:
            sse_unsub()
        for subscription_id in self.listeners[UART]:
            UartEventBus.unsubscribe(subscription_id)

        # unload all platform entities
        unload_ok = await self.hass.config_entries.async_forward_entry_unload(
            self.config_entry, LIGHT_PLATFORM
        )

        return unload_ok

    @callback
    def on_close(self, event: Event) -> None:
        """Close SSE client and uart bridge."""
        _LOGGER.debug(event.data)
        if self.sse is not None:
            self.sse.close_client()
        if self.uart is not None:
            self.uart.stop()


async def options_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
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

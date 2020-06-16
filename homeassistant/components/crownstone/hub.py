"""Code to set up all communications with Crownstones."""
import asyncio
import logging
from typing import Optional

from crownstone_cloud import CrownstoneCloud
from crownstone_cloud.exceptions import (
    CrownstoneAuthenticationError,
    CrownstoneUnknownError,
)
from crownstone_cloud.lib.cloudModels.spheres import Sphere
from crownstone_sse import CrownstoneSSE
from crownstone_sse.const import (
    EVENT_PRESENCE_ENTER_LOCATION,
    EVENT_PRESENCE_ENTER_SPHERE,
    EVENT_PRESENCE_EXIT_SPHERE,
)
from crownstone_sse.events.PresenceEvent import PresenceEvent

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import CONF_SPHERE, DOMAIN
from .helpers import UartManager

_LOGGER = logging.getLogger(__name__)


class CrownstoneHub:
    """Manage all Crownstone IO."""

    def __init__(self, hass, config_entry) -> None:
        """Initialize the hub."""
        self.sphere: Optional[Sphere] = None
        self.config_entry: ConfigEntry = config_entry
        self.hass: HomeAssistant = hass
        self.cloud: Optional[CrownstoneCloud] = None
        self.uart_manager: Optional[UartManager] = None
        self.sse: Optional[CrownstoneSSE] = None

    async def async_setup(self) -> bool:
        """
        Set up the Crownstone hub.

        The hub is a combination of Crownstone cloud, Crownstone SSE and Crownstone uart.
        Returns True if the setup was successful.
        """
        # Setup email and password gained from config flow
        customer_email = self.config_entry.data[CONF_EMAIL]
        customer_password = self.config_entry.data[CONF_PASSWORD]

        # Create cloud instance
        self.cloud = CrownstoneCloud(
            email=customer_email,
            password=customer_password,
            loop=self.hass.loop,
            websession=aiohttp_client.async_get_clientsession(self.hass),
        )
        # Login
        try:
            await self.cloud.initialize()
        except CrownstoneAuthenticationError as auth_err:
            _LOGGER.error(
                "Auth error during login with type: %s and message: %s",
                auth_err.type,
                auth_err.message,
            )
            return False
        except CrownstoneUnknownError:
            _LOGGER.error("Unknown error during login")
            raise ConfigEntryNotReady

        # set the sphere we chose to setup in the flow
        self.sphere = self.cloud.spheres.find(self.config_entry.data[CONF_SPHERE])

        # Create uart manager to manage usb connections
        # uart.is_ready() returns whether the usb is ready or not.
        self.uart_manager = UartManager()
        self.uart_manager.start()

        # Create SSE instance
        self.sse = CrownstoneSSE(customer_email, customer_password)
        self.sse.set_access_token(self.cloud.get_access_token())
        self.sse.start()

        # presence updates
        self.sse.add_event_listener(EVENT_PRESENCE_ENTER_SPHERE, self.update_presence)
        self.sse.add_event_listener(EVENT_PRESENCE_ENTER_LOCATION, self.update_presence)
        self.sse.add_event_listener(EVENT_PRESENCE_EXIT_SPHERE, self.update_presence)

        # create listener for when home assistant is stopped
        self.hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, self.async_stop)

        # register presence entities
        self.hass.async_create_task(
            self.hass.config_entries.async_forward_entry_setup(
                self.config_entry, "sensor"
            )
        )

        # register crownstone entities
        self.hass.async_create_task(
            self.hass.config_entries.async_forward_entry_setup(
                self.config_entry, "light"
            )
        )

        return True

    async def async_reset(self) -> bool:
        """
        Reset the hub after entry removal.

        Config flow will ensure the right email and password are provided.
        If an authentication error still occurs, return.

        If the setup was successful, unload forwarded entry.
        """
        # reset RequestHandler instance
        self.cloud.reset()
        # stop uart
        self.uart_manager.stop()
        # stop sse client
        await self.sse.async_stop()

        # authentication failed
        if self.cloud.spheres is None:
            return True

        # unload all platform entities
        results = await asyncio.gather(
            self.hass.config_entries.async_forward_entry_unload(
                self.config_entry, "sensor"
            ),
            self.hass.config_entries.async_forward_entry_unload(
                self.config_entry, "light"
            ),
        )

        return False not in results

    @callback
    def update_presence(self, presence_event: PresenceEvent) -> None:
        """Update the presence in a location or in the sphere."""
        update_sphere = self.cloud.spheres.find_by_id(presence_event.sphere_id)
        if update_sphere.cloud_id == self.sphere.cloud_id:
            user = self.sphere.users.find_by_id(presence_event.user_id)

            if presence_event.type == EVENT_PRESENCE_ENTER_LOCATION:
                # remove the user from all locations
                # a user can only be in one location at the time, so make sure there are no duplicates.
                # we only have to listen for enter location, to see a data change.
                for location in self.sphere.locations:
                    if user.cloud_id in location.present_people:
                        location.present_people.remove(user.cloud_id)
                # add the user in the entered location
                location_entered = self.sphere.locations.find_by_id(
                    presence_event.location_id
                )
                location_entered.present_people.append(user.cloud_id)

            if presence_event.type == EVENT_PRESENCE_ENTER_SPHERE:
                # check if the user id is already in the sphere.
                if user.cloud_id in self.sphere.present_people:
                    # do nothing
                    pass
                else:
                    # add user to the present people
                    self.sphere.present_people.append(user.cloud_id)

            if presence_event.type == EVENT_PRESENCE_EXIT_SPHERE:
                # user has left the sphere.
                # remove the user from the present people.
                self.sphere.present_people.remove(user.cloud_id)

        # send signal for state update
        async_dispatcher_send(self.hass, DOMAIN)

    @callback
    async def async_stop(self, event: Event) -> None:
        """Close SSE client (thread) and uart bridge."""
        await self.sse.async_stop()
        self.uart_manager.stop()

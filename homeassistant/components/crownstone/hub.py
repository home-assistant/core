"""Code to set up all communications with Crownstones."""
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
    EVENT_ABILITY_CHANGE_DIMMING,
    EVENT_ABILITY_CHANGE_SWITCHCRAFT,
    EVENT_ABILITY_CHANGE_TAP_TO_TOGGLE,
)
from crownstone_sse.events.AbilityChangeEvent import AbilityChangeEvent

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import aiohttp_client

from .const import CONF_SPHERE, LIGHT_PLATFORM
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
            websession=aiohttp_client.async_get_clientsession(self.hass),
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

        # subscribe to Crownstone ability updates
        self.sse.add_event_listener(EVENT_ABILITY_CHANGE_DIMMING, self.update_ability)
        self.sse.add_event_listener(
            EVENT_ABILITY_CHANGE_SWITCHCRAFT, self.update_ability
        )
        self.sse.add_event_listener(
            EVENT_ABILITY_CHANGE_TAP_TO_TOGGLE, self.update_ability
        )

        # create listener for when home assistant is stopped
        self.hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, self.async_stop)

        # register crownstone entities
        self.hass.async_create_task(
            self.hass.config_entries.async_forward_entry_setup(
                self.config_entry, LIGHT_PLATFORM
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
        result = await self.hass.config_entries.async_forward_entry_unload(
            self.config_entry, LIGHT_PLATFORM
        )

        return result is not False

    @callback
    def update_ability(self, ability_event: AbilityChangeEvent) -> None:
        """Update the ability information."""
        # make sure the sphere matches current.
        update_sphere = self.cloud.spheres.find_by_id(ability_event.sphere_id)
        if update_sphere.cloud_id == self.sphere.cloud_id:
            update_crownstone = self.sphere.crownstones.find_by_uid(
                ability_event.unique_id
            )
            if update_crownstone is not None:
                # write the change to the crownstone entity.
                update_crownstone.abilities[
                    ability_event.ability_type
                ].is_enabled = ability_event.ability_enabled
                # reload the config entry to process the change in supported features
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self.config_entry.entry_id)
                )

    @callback
    async def async_stop(self, event: Event) -> None:
        """Close SSE client (thread) and uart bridge."""
        await self.sse.async_stop()
        self.uart_manager.stop()

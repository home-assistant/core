"""Extend the basic Accessory and Bridge functions."""
from datetime import timedelta
from functools import partial, wraps
from inspect import getmodule
import logging

from pyhap.accessory import Accessory, Bridge
from pyhap.accessory_driver import AccessoryDriver
from pyhap.const import CATEGORY_OTHER

from homeassistant.const import __version__
from homeassistant.core import callback as ha_callback
from homeassistant.core import split_entity_id
from homeassistant.helpers.event import (
    async_track_state_change, track_point_in_utc_time)
from homeassistant.util import dt as dt_util

from .const import (
    BRIDGE_MODEL, BRIDGE_NAME, BRIDGE_SERIAL_NUMBER,
    DEBOUNCE_TIMEOUT, MANUFACTURER)
from .util import (
    show_setup_message, dismiss_setup_message)

_LOGGER = logging.getLogger(__name__)


def debounce(func):
    """Decorator function. Debounce callbacks form HomeKit."""
    @ha_callback
    def call_later_listener(self, *args):
        """Callback listener called from call_later."""
        debounce_params = self.debounce.pop(func.__name__, None)
        if debounce_params:
            self.hass.async_add_job(func, self, *debounce_params[1:])

    @wraps(func)
    def wrapper(self, *args):
        """Wrapper starts async timer."""
        debounce_params = self.debounce.pop(func.__name__, None)
        if debounce_params:
            debounce_params[0]()  # remove listener
        remove_listener = track_point_in_utc_time(
            self.hass, partial(call_later_listener, self),
            dt_util.utcnow() + timedelta(seconds=DEBOUNCE_TIMEOUT))
        self.debounce[func.__name__] = (remove_listener, *args)
        logger.debug('%s: Start %s timeout', self.entity_id,
                     func.__name__.replace('set_', ''))

    name = getmodule(func).__name__
    logger = logging.getLogger(name)
    return wrapper


class HomeAccessory(Accessory):
    """Adapter class for Accessory."""

    def __init__(self, hass, driver, name, entity_id, aid, config,
                 category=CATEGORY_OTHER):
        """Initialize a Accessory object."""
        super().__init__(driver, name, aid=aid)
        model = split_entity_id(entity_id)[0].replace("_", " ").title()
        self.set_info_service(
            firmware_revision=__version__, manufacturer=MANUFACTURER,
            model=model, serial_number=entity_id)
        self.category = category
        self.config = config
        self.entity_id = entity_id
        self.hass = hass
        self.debounce = {}

    async def run(self):
        """Method called by accessory after driver is started.

        Run inside the HAP-python event loop.
        """
        state = self.hass.states.get(self.entity_id)
        self.hass.add_job(self.update_state_callback, None, None, state)
        async_track_state_change(
            self.hass, self.entity_id, self.update_state_callback)

    @ha_callback
    def update_state_callback(self, entity_id=None, old_state=None,
                              new_state=None):
        """Callback from state change listener."""
        _LOGGER.debug('New_state: %s', new_state)
        if new_state is None:
            return
        self.hass.async_add_job(self.update_state, new_state)

    def update_state(self, new_state):
        """Method called on state change to update HomeKit value.

        Overridden by accessory types.
        """
        raise NotImplementedError()


class HomeBridge(Bridge):
    """Adapter class for Bridge."""

    def __init__(self, hass, driver, name=BRIDGE_NAME):
        """Initialize a Bridge object."""
        super().__init__(driver, name)
        self.set_info_service(
            firmware_revision=__version__, manufacturer=MANUFACTURER,
            model=BRIDGE_MODEL, serial_number=BRIDGE_SERIAL_NUMBER)
        self.hass = hass

    def setup_message(self):
        """Prevent print of pyhap setup message to terminal."""
        pass


class HomeDriver(AccessoryDriver):
    """Adapter class for AccessoryDriver."""

    def __init__(self, hass, **kwargs):
        """Initialize a AccessoryDriver object."""
        super().__init__(**kwargs)
        self.hass = hass

    def pair(self, client_uuid, client_public):
        """Override super function to dismiss setup message if paired."""
        success = super().pair(client_uuid, client_public)
        if success:
            dismiss_setup_message(self.hass)
        return success

    def unpair(self, client_uuid):
        """Override super function to show setup message if unpaired."""
        super().unpair(client_uuid)
        show_setup_message(self.hass, self.state.pincode)

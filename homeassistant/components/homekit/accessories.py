"""Extend the basic Accessory and Bridge functions."""
from datetime import timedelta
from functools import wraps
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
    def call_later_listener(*args):
        """Callback listener called from call_later."""
        # pylint: disable=unsubscriptable-object
        nonlocal lastargs, remove_listener
        hass = lastargs['hass']
        hass.async_add_job(func, *lastargs['args'])
        lastargs = remove_listener = None

    @wraps(func)
    def wrapper(*args):
        """Wrapper starts async timer.

        The accessory must have 'self.hass' and 'self.entity_id' as attributes.
        """
        # pylint: disable=not-callable
        hass = args[0].hass
        nonlocal lastargs, remove_listener
        if remove_listener:
            remove_listener()
            lastargs = remove_listener = None
        lastargs = {'hass': hass, 'args': [*args]}
        remove_listener = track_point_in_utc_time(
            hass, call_later_listener,
            dt_util.utcnow() + timedelta(seconds=DEBOUNCE_TIMEOUT))
        logger.debug('%s: Start %s timeout', args[0].entity_id,
                     func.__name__.replace('set_', ''))

    remove_listener = None
    lastargs = None
    name = getmodule(func).__name__
    logger = logging.getLogger(name)
    return wrapper


class HomeAccessory(Accessory):
    """Adapter class for Accessory."""

    def __init__(self, hass, name, entity_id, aid, config,
                 category=CATEGORY_OTHER):
        """Initialize a Accessory object."""
        super().__init__(name, aid=aid)
        model = split_entity_id(entity_id)[0].replace("_", " ").title()
        self.set_info_service(
            firmware_revision=__version__, manufacturer=MANUFACTURER,
            model=model, serial_number=entity_id)
        self.category = category
        self.config = config
        self.entity_id = entity_id
        self.hass = hass

    def run(self):
        """Method called by accessory after driver is started."""
        state = self.hass.states.get(self.entity_id)
        self.update_state_callback(new_state=state)
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

    def __init__(self, hass, name=BRIDGE_NAME):
        """Initialize a Bridge object."""
        super().__init__(name)
        self.set_info_service(
            firmware_revision=__version__, manufacturer=MANUFACTURER,
            model=BRIDGE_MODEL, serial_number=BRIDGE_SERIAL_NUMBER)
        self.hass = hass

    def setup_message(self):
        """Prevent print of pyhap setup message to terminal."""
        pass


class HomeDriver(AccessoryDriver):
    """Adapter class for AccessoryDriver."""

    def __init__(self, hass, *args, **kwargs):
        """Initialize a AccessoryDriver object."""
        super().__init__(*args, **kwargs)
        self.hass = hass

    def pair(self, client_uuid, client_public):
        """Override super function to dismiss setup message if paired."""
        value = super().pair(client_uuid, client_public)
        if value:
            dismiss_setup_message(self.hass)
        return value

    def unpair(self, client_uuid):
        """Override super function to show setup message if unpaired."""
        super().unpair(client_uuid)
        show_setup_message(self.hass, self.state.pincode)

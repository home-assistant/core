"""Extend the basic Accessory and Bridge functions."""
import logging

from pyhap.accessory import Accessory, Bridge, Category
from pyhap.accessory_driver import AccessoryDriver

from homeassistant.helpers.event import async_track_state_change

from .const import (
    ACCESSORY_MODEL, ACCESSORY_NAME, BRIDGE_MODEL, BRIDGE_NAME,
    MANUFACTURER, SERV_ACCESSORY_INFO, CHAR_MANUFACTURER, CHAR_MODEL,
    CHAR_NAME, CHAR_SERIAL_NUMBER)
from .util import (
    show_setup_message, dismiss_setup_message)

_LOGGER = logging.getLogger(__name__)


def add_preload_service(acc, service, chars=None):
    """Define and return a service to be available for the accessory."""
    from pyhap.loader import get_serv_loader, get_char_loader
    service = get_serv_loader().get(service)
    if chars:
        chars = chars if isinstance(chars, list) else [chars]
        for char_name in chars:
            char = get_char_loader().get(char_name)
            service.add_characteristic(char)
    acc.add_service(service)
    return service


def set_accessory_info(acc, name, model, manufacturer=MANUFACTURER,
                       serial_number='0000'):
    """Set the default accessory information."""
    service = acc.get_service(SERV_ACCESSORY_INFO)
    service.get_characteristic(CHAR_NAME).set_value(name)
    service.get_characteristic(CHAR_MODEL).set_value(model)
    service.get_characteristic(CHAR_MANUFACTURER).set_value(manufacturer)
    service.get_characteristic(CHAR_SERIAL_NUMBER).set_value(serial_number)


class HomeAccessory(Accessory):
    """Adapter class for Accessory."""

    # pylint: disable=no-member

    def __init__(self, name=ACCESSORY_NAME, model=ACCESSORY_MODEL,
                 category='OTHER', **kwargs):
        """Initialize a Accessory object."""
        super().__init__(name, **kwargs)
        set_accessory_info(self, name, model)
        self.category = getattr(Category, category, Category.OTHER)

    def _set_services(self):
        add_preload_service(self, SERV_ACCESSORY_INFO)

    def run(self):
        """Method called by accessory after driver is started."""
        state = self.hass.states.get(self.entity_id)
        self.update_state(new_state=state)
        async_track_state_change(
            self.hass, self.entity_id, self.update_state)


class HomeBridge(Bridge):
    """Adapter class for Bridge."""

    def __init__(self, hass, name=BRIDGE_NAME,
                 model=BRIDGE_MODEL, **kwargs):
        """Initialize a Bridge object."""
        super().__init__(name, **kwargs)
        set_accessory_info(self, name, model)
        self.hass = hass

    def _set_services(self):
        add_preload_service(self, SERV_ACCESSORY_INFO)

    def setup_message(self):
        """Prevent print of pyhap setup message to terminal."""
        pass

    def add_paired_client(self, client_uuid, client_public):
        """Override super function to dismiss setup message if paired."""
        super().add_paired_client(client_uuid, client_public)
        dismiss_setup_message(self.hass)

    def remove_paired_client(self, client_uuid):
        """Override super function to show setup message if unpaired."""
        super().remove_paired_client(client_uuid)
        show_setup_message(self, self.hass)


class HomeDriver(AccessoryDriver):
    """Adapter class for AccessoryDriver."""

    def __init__(self, *args, **kwargs):
        """Initialize a AccessoryDriver object."""
        super().__init__(*args, **kwargs)

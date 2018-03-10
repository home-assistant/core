"""Extend the basic Accessory and Bridge functions."""
import logging

from pyhap.accessory import Accessory, Bridge, Category

from .const import (
    SERV_ACCESSORY_INFO, SERV_BRIDGING_STATE, MANUFACTURER,
    CHAR_MODEL, CHAR_MANUFACTURER, CHAR_NAME, CHAR_SERIAL_NUMBER)


_LOGGER = logging.getLogger(__name__)


def set_accessory_info(acc, name, model, manufacturer=MANUFACTURER,
                       serial_number='0000'):
    """Set the default accessory information."""
    service = acc.get_service(SERV_ACCESSORY_INFO)
    service.get_characteristic(CHAR_NAME).set_value(name)
    service.get_characteristic(CHAR_MODEL).set_value(model)
    service.get_characteristic(CHAR_MANUFACTURER).set_value(manufacturer)
    service.get_characteristic(CHAR_SERIAL_NUMBER).set_value(serial_number)


def add_preload_service(acc, service, chars=None, opt_chars=None):
    """Define and return a service to be available for the accessory."""
    from pyhap.loader import get_serv_loader, get_char_loader
    service = get_serv_loader().get(service)
    if chars:
        chars = chars if isinstance(chars, list) else [chars]
        for char_name in chars:
            char = get_char_loader().get(char_name)
            service.add_characteristic(char)
    if opt_chars:
        opt_chars = opt_chars if isinstance(opt_chars, list) else [opt_chars]
        for opt_char_name in opt_chars:
            opt_char = get_char_loader().get(opt_char_name)
            service.add_opt_characteristic(opt_char)
    acc.add_service(service)
    return service


def override_properties(char, new_properties):
    """Override characteristic property values."""
    char.properties.update(new_properties)


class HomeAccessory(Accessory):
    """Class to extend the Accessory class."""

    def __init__(self, display_name, model, category='OTHER', **kwargs):
        """Initialize a Accessory object."""
        super().__init__(display_name, **kwargs)
        set_accessory_info(self, display_name, model)
        self.category = getattr(Category, category, Category.OTHER)

    def _set_services(self):
        add_preload_service(self, SERV_ACCESSORY_INFO)


class HomeBridge(Bridge):
    """Class to extend the Bridge class."""

    def __init__(self, display_name, model, pincode, **kwargs):
        """Initialize a Bridge object."""
        super().__init__(display_name, pincode=pincode, **kwargs)
        set_accessory_info(self, display_name, model)

    def _set_services(self):
        add_preload_service(self, SERV_ACCESSORY_INFO)
        add_preload_service(self, SERV_BRIDGING_STATE)

"""Extend the basic Accessory and Bridge functions."""
from pyhap.accessory import Accessory, Bridge, Category

from .const import (
    SERVICES_ACCESSORY_INFO, MANUFACTURER,
    CHAR_MODEL, CHAR_MANUFACTURER, CHAR_SERIAL_NUMBER)


class HomeAccessory(Accessory):
    """Class to extend the Accessory class."""

    ALL_CATEGORIES = Category

    def __init__(self, display_name):
        """Initialize a Accessory object."""
        super().__init__(display_name)

    def set_category(self, category):
        """Set the category of the accessory."""
        self.category = category

    def add_preload_service(self, service):
        """Define the services to be available for the accessory."""
        from pyhap.loader import get_serv_loader
        self.add_service(get_serv_loader().get(service))

    def set_accessory_info(self, model, manufacturer=MANUFACTURER,
                           serial_number='0000'):
        """Set the default accessory information."""
        service_info = self.get_service(SERVICES_ACCESSORY_INFO)
        service_info.get_characteristic(CHAR_MODEL) \
                    .set_value(model)
        service_info.get_characteristic(CHAR_MANUFACTURER) \
                    .set_value(manufacturer)
        service_info.get_characteristic(CHAR_SERIAL_NUMBER) \
                    .set_value(serial_number)


class HomeBridge(Bridge):
    """Class to extend the Bridge class."""

    def __init__(self, display_name, pincode):
        """Initialize a Bridge object."""
        super().__init__(display_name, pincode=pincode)

    def set_accessory_info(self, model, manufacturer=MANUFACTURER,
                           serial_number='0000'):
        """Set the default accessory information."""
        service_info = self.get_service(SERVICES_ACCESSORY_INFO)
        service_info.get_characteristic(CHAR_MODEL) \
                    .set_value(model)
        service_info.get_characteristic(CHAR_MANUFACTURER) \
                    .set_value(manufacturer)
        service_info.get_characteristic(CHAR_SERIAL_NUMBER) \
                    .set_value(serial_number)

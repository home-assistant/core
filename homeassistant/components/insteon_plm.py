"""
Support for INSTEON PowerLinc Modem.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/insteon_plm/
"""
import logging
import asyncio
import collections

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import (
    CONF_PORT, EVENT_HOMEASSISTANT_STOP)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery

from insteonplm.constants import *

REQUIREMENTS = ['insteonplm==0.7.5']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'insteon_plm'

CONF_OVERRIDE = 'device_override'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PORT): cv.string,
        vol.Optional(CONF_OVERRIDE, default=[]): vol.All(
            cv.ensure_list_csv, vol.Length(min=1))
    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the connection to the PLM."""
    import insteonplm
    ipdb = IPDB()

    conf = config[DOMAIN]
    port = conf.get(CONF_PORT)
    overrides = conf.get(CONF_OVERRIDE)

    @callback
    def async_plm_new_device(device):
        """Detect device from transport to be delegated to platform."""
        _LOGGER = logging.getLogger(__name__)
        _LOGGER.debug('Starting Home-Assistant async_plm_new_device')
        _LOGGER.debug(device)
        name = device.id
        address = device.address.human
        product = ipdb[[device.cat, device.subcat, device.groupbutton]]

        _LOGGER.info("New INSTEON PLM device: %s (%s) %s",
                     name, address, product[4])
        if product[4] is not None:
            hass.async_add_job(
                discovery.async_load_platform(
                    hass, product[4], DOMAIN, discovered=[device],
                    hass_config=config))

        _LOGGER.debug('Starting Home-Assistant async_plm_new_device')

    _LOGGER.info("Looking for PLM on %s", port)
    plm = yield from insteonplm.Connection.create(device=port, loop=hass.loop)

    for device_override in overrides:
        #
        # Override the device default capabilities for a specific address
        #
        if device_override.get('cat', False):
            plm.protocol.devices.add_override(
                    device_override['address'], 'cat', device_override['cat'])
        if device_override.get('subcat', False):
            plm.protocol.devices.add_override(
                    device_override['address'], 'subcat', device_override['subcat'])
        if device_override.get('firmware', False):
            plm.protocol.devices.add_override(
                    device_override['address'], 'product_key', device_override['firmware'])
        if device_override.get('product_key', False):
            plm.protocol.devices.add_override(
                device_override['address'], 'product_key', device_override['product_key'])

    hass.data['insteon_plm'] = plm

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, plm.close)

    plm.protocol.devices.add_device_callback(async_plm_new_device)

    return True

def common_attributes(entity):
    """Return the device state attributes."""
    attributes = {
        'INSTEON Address' : entity.address.human,
        'Description': entity.description,
        'Model': entity.model,
        'Category': '{:02x}'.format(entity.cat),
        'Subcategory': '{:02x}'.format(entity.subcat),
        'Product Key / Firmware': '{:02x}'.format(entity.product_key),
        'Group': entity.groupbutton
    }
    return attributes


Product = collections.namedtuple('Product', 'cat subcat product_key group platform')

class IPDB(object):
    """Embodies the INSTEON Product Database static data and access methods."""

    products = [
        
        Product(DEVICE_CATEGORY_GENERALIZED_CONTROLLERS_0X00, None, None, None, None),
        Product(DEVICE_CATEGORY_DIMMABLE_LIGHTING_CONTROL_0X01, None, None, None, 'light'),
        Product(DEVICE_CATEGORY_DIMMABLE_LIGHTING_CONTROL_0X01, 0x2e, None, 0x01, 'light'),  # FanLinc Light
        Product(DEVICE_CATEGORY_DIMMABLE_LIGHTING_CONTROL_0X01, 0x2e, None, 0x02, 'fan'),    # FanLinc Fan
        Product(DEVICE_CATEGORY_SWITCHED_LIGHTING_CONTROL_0X02, None, None, None, 'switch'),
        Product(DEVICE_CATEGORY_SWITCHED_LIGHTING_CONTROL_0X02, 0x39, None, 0x01, 'switch'), # On/Off Outlet Top
        Product(DEVICE_CATEGORY_SWITCHED_LIGHTING_CONTROL_0X02, 0x39, None, 0x02, 'switch'), # On/Off Outlet Bottom
        Product(DEVICE_CATEGORY_NETWORK_BRIDGES_0X03, None, None, None, None),
        Product(DEVICE_CATEGORY_IRRIGATION_CONTROL_0X04, None, None, None, None),
        Product(DEVICE_CATEGORY_CLIMATE_CONTROL_0X05, None, None, None, None),
        Product(DEVICE_CATEGORY_SENSORS_AND_ACTUATORS_0X07, None, None, None, None),
        Product(DEVICE_CATEGORY_SENSORS_AND_ACTUATORS_0X07, 0x00, None, 0x01, 'switch'),  # Relay of the I/O Linc
        Product(DEVICE_CATEGORY_SENSORS_AND_ACTUATORS_0X07, 0x00, None, 0x02, 'binary_sensor'), # Sensor of the I/O Linc
        Product(DEVICE_CATEGORY_HOME_ENTERTAINMENT_0X08, None, None, None, None),
        Product(DEVICE_CATEGORY_ENERGY_MANAGEMENT_0X09, None, None, None, None),
        Product(DEVICE_CATEGORY_BUILT_IN_APPLIANCE_CONTROL_0X0A, None, None, None, None),
        Product(DEVICE_CATEGORY_PLUMBING_0X0B, None, None, None, None),
        Product(DEVICE_CATEGORY_COMMUNICATION_0X0C, None, None, None, None),
        Product(DEVICE_CATEGORY_COMPUTER_CONTROL_0X0D, None, None, None, None),
        Product(DEVICE_CATEGORY_WINDOW_COVERINGS_0X0E, None, None, None, None),
        Product(DEVICE_CATEGORY_ACCESS_CONTROL_0X0F, None, None, None, None),
        Product(DEVICE_CATEGORY_SECURITY_HEALTH_SAFETY_0X10, None, None, None, 'sensor'), # making the default sensor since this is more flexible than binary_sensor
        Product(DEVICE_CATEGORY_SECURITY_HEALTH_SAFETY_0X10, 0x01, None, None, 'binary_sensor'),        
        Product(DEVICE_CATEGORY_SECURITY_HEALTH_SAFETY_0X10, 0x02, None, None, 'binary_sensor'),
        Product(DEVICE_CATEGORY_SECURITY_HEALTH_SAFETY_0X10, 0x08, None, None, 'binary_sensor'),
        Product(DEVICE_CATEGORY_SECURITY_HEALTH_SAFETY_0X10, 0x11, None, None, 'binary_sensor'),
        Product(DEVICE_CATEGORY_SURVEILLANCE_0X11, None, None, None, None),
        Product(DEVICE_CATEGORY_AUTOMOTIVE_0X12, None, None, None, None),
        Product(DEVICE_CATEGORY_PET_CARE_0X13, None, None, None, None),
        Product(DEVICE_CATEGORY_TIMEKEEPING_0X15, None, None, None, None),
        Product(DEVICE_CATEGORY_HOLIDAY_0X16, None, None, None, None)
    ]

    def __init__(self):
        self.log = logging.getLogger(__name__)

    def __len__(self):
        return len(self.products)

    def __iter__(self):
        for product in self.products:
            yield product

    def __getitem__(self, key):
        cat, subcat, group = key

        # Check for a group specific device first
        for product in self.products:
            if cat == product.cat and subcat == product.subcat and group == product.group:
                return product

        # Check for a non-group sepecific device
        for product in self.products:
            if cat == product.cat and subcat == product.subcat:
                return product

        # We failed to find a device in the database, so we will make a best
        # guess from the cat and return the generic class
        #
        
        for product in self.products:
            if cat == product.cat and product.subcat == None:
                return product

        # We did not find the device or even a generic device of that category
        return Product(cat, subcat, None, None) 

import json
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from pizzapi import Customer, Address, Order
from homeassistant.helpers.entity import Entity
import unicodedata


_LOGGER = logging.getLogger(__name__)


# The domain of your component. Should be equal to the name of your component.
DOMAIN = 'dominos'

ATTR_COUNTRY = 'country_code'
ATTR_FIRST_NAME = 'first_name'
ATTR_LAST_NAME = 'last_name'
ATTR_EMAIL = 'email'
ATTR_PHONE = 'phone'
ATTR_ADDRESS = 'address'
ATTR_ORDERS = 'orders'
ATTR_DUMP_MENU = 'dump_menu'
ATTR_ORDER_ENTITY = 'order_entity_id'

COMMIT = '183d0f5522e7fa99776e8c6c692b56e69f0e6b8f'
REQUIREMENTS = [
    'https://github.com/wardcraigj/pizzapi/archive/%s.zip#pizzapi==0.0.2' % COMMIT]

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(ATTR_COUNTRY): cv.string,
        vol.Required(ATTR_FIRST_NAME): cv.string,
        vol.Required(ATTR_LAST_NAME): cv.string,
        vol.Required(ATTR_EMAIL): cv.string,
        vol.Required(ATTR_PHONE): cv.string,
        vol.Required(ATTR_ADDRESS): cv.string,
        vol.Optional(ATTR_ORDERS): cv.ensure_list,
        vol.Optional(ATTR_DUMP_MENU): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""
    dominos = Dominos(hass, config)

    hass.data[DOMAIN] = []

    if config[DOMAIN].get(ATTR_DUMP_MENU):
        dominos.dump_menu(hass)

    for order in config[DOMAIN].get(ATTR_ORDERS):
        # _LOGGER.INFO('Creating Order')
        hass.states.set(
            'dominos.' + order['name'].replace(" ", "_"), json.dumps(order['codes']))
    hass.services.register(DOMAIN, 'order', dominos.handle_order)

    # Return boolean to indicate that initialization was successfully.
    return True


class Dominos():

    def __init__(self, hass, config):
        self.hass = hass
        self.customer = Customer(config[DOMAIN].get(ATTR_FIRST_NAME), config[DOMAIN].get(
            ATTR_LAST_NAME), config[DOMAIN].get(ATTR_EMAIL), config[DOMAIN].get(ATTR_PHONE), config[DOMAIN].get(ATTR_ADDRESS))
        self.address = Address(
            *self.customer.address.split(','), country=config[DOMAIN].get(ATTR_COUNTRY))
        self.country = config[DOMAIN].get(ATTR_COUNTRY)

    def handle_order(self, call=None):
        """Handle ordering pizza."""

        store = self.address.closest_store()

        order_key = call.data.get(ATTR_ORDER_ENTITY)
        state = self.hass.states._states[order_key]
        order_codes = json.loads(state.state)

        order = Order(store, self.customer, self.address, self.country)

        for code in order_codes:
            order.add_item(code['code'])

        order.place()

    def dump_menu(self, hass):

        store = self.address.closest_store()
        menu = store.get_menu()
        for product in menu.products:
            if isinstance(product.menu_data['Variants'], list):
                variants = ', '.join(product.menu_data['Variants'])
            else:
                variants = product.menu_data['Variants']
            
            message = 'name: ' + product.name + ' variants: ' + variants
            
            #We get some weird product names sometimes, so clobber this to make it logger safe
            _LOGGER.warning(unicodedata.normalize('NFKC', message).encode('ascii','ignore').decode('ascii'))

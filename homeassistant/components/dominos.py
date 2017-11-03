import json
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from pizzapi import Customer, Address, Order
import jsonpickle
from homeassistant.helpers.entity import Entity

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

COMMIT = 'ae140bd640d64ce5fdb638d5b11cfc8dae6c6587'
REQUIREMENTS = ['https://github.com/wardcraigj/pizzapi/archive/%s.zip#pizzapi==0.0.2' % COMMIT, 'jsonpickle']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(ATTR_COUNTRY): cv.string,
        vol.Required(ATTR_FIRST_NAME): cv.string,
        vol.Required(ATTR_LAST_NAME): cv.string,
        vol.Required(ATTR_EMAIL): cv.string,
        vol.Required(ATTR_PHONE): cv.string,
        vol.Required(ATTR_ADDRESS): cv.string,
        vol.Optional(ATTR_ORDERS) : cv.ensure_list,
        vol.Optional(ATTR_DUMP_MENU) : cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""
    dominos = Dominos(hass, config)

    hass.data[DOMAIN] = []

    if config[DOMAIN].get(ATTR_DUMP_MENU):
        dominos.create_product_entities(hass)

    for order in config[DOMAIN].get(ATTR_ORDERS):
        # _LOGGER.INFO('Creating Order')
        hass.states.set('dominos.' + order['name'].replace(" ", "_"), json.dumps(order['codes']))
    hass.services.register(DOMAIN, 'order', dominos.handle_order)


    # Return boolean to indicate that initialization was successfully.
    return True

class Dominos():

    def __init__(self, hass, config):
        self.hass = hass
        self.customer = Customer(config[DOMAIN].get(ATTR_FIRST_NAME), config[DOMAIN].get(
        ATTR_LAST_NAME), config[DOMAIN].get(ATTR_EMAIL), config[DOMAIN].get(ATTR_PHONE), config[DOMAIN].get(ATTR_ADDRESS))
        self.address = Address(*self.customer.address.split(','), country=config[DOMAIN].get(ATTR_COUNTRY))
        self.store = self.address.closest_store()
        self.country = config[DOMAIN].get(ATTR_COUNTRY) 

    def handle_order(self, call=None):
        """Handle ordering pizza."""

        order_key = call.data.get(ATTR_ORDER_ENTITY)
        state = self.hass.states._states[order_key]
        order_codes = json.loads(state.state)

        order = Order(self.store, self.customer,self.address, self.country)

        for code in order_codes:
            order.add_item(code['code'])

        order.place()

        _LOGGER.warning('here')

    def create_product_entities(self, hass):
        menu = self.store.get_menu()
        for product in menu.products:
            _LOGGER.warning('name: ' + product.name + ' variants: ' + ''.join(product.menu_data['Variants']))

        _LOGGER.warning('here')



class DominosProduct(Entity):

    def __init__(self, menu_item):
        self._name = menu_item.name
        self._variants = menu_item.menu_data['Variants']

    @property
    def name(self):
        return self._name

    @property
    def variants(self):
        return self._variants

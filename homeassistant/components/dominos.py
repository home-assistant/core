import logging
import unicodedata
from datetime import timedelta

import voluptuous as vol
import time

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity, generate_entity_id
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util import Throttle
from pizzapi import Address, Customer, Order

_LOGGER = logging.getLogger(__name__)


# The domain of your component. Should be equal to the name of your component.
DOMAIN = 'dominos'
ENTITY_ID_FORMAT = DOMAIN + '.{}'

ATTR_COUNTRY = 'country_code'
ATTR_FIRST_NAME = 'first_name'
ATTR_LAST_NAME = 'last_name'
ATTR_EMAIL = 'email'
ATTR_PHONE = 'phone'
ATTR_ADDRESS = 'address'
ATTR_ORDERS = 'orders'
ATTR_DUMP_MENU = 'dump_menu'
ATTR_ORDER_ENTITY = 'order_entity_id'
ATTR_ORDER_NAME = 'name'
ATTR_ORDER_CODES = 'codes'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)
MIN_TIME_BETWEEN_STORE_UPDATES = 1800

REV = '183d0f5522e7fa99776e8c6c692b56e69f0e6b8f'
REQUIREMENTS = [
    'https://github.com/wardcraigj/pizzapi/archive/%s.zip#pizzapi==0.0.2'
    % REV]

_ORDERS_SCHEMA = vol.Schema({
    vol.Required(ATTR_ORDER_NAME): cv.string,
    vol.Required(ATTR_ORDER_CODES): vol.All(cv.ensure_list, [cv.string]),
})


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(ATTR_COUNTRY): cv.string,
        vol.Required(ATTR_FIRST_NAME): cv.string,
        vol.Required(ATTR_LAST_NAME): cv.string,
        vol.Required(ATTR_EMAIL): cv.string,
        vol.Required(ATTR_PHONE): cv.string,
        vol.Required(ATTR_ADDRESS): cv.string,
        vol.Optional(ATTR_DUMP_MENU): cv.boolean,
        vol.Optional(ATTR_ORDERS): vol.All(cv.ensure_list, [_ORDERS_SCHEMA]),
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""
    dominos = Dominos(hass, config)

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]['entities'] = []

    hass.services.register(DOMAIN, 'order', dominos.handle_order)

    if config[DOMAIN].get(ATTR_DUMP_MENU):
        dominos.dump_menu(hass)

    for order_info in config[DOMAIN].get(ATTR_ORDERS):
        hass.data[DOMAIN]['entities'].append(DominosOrder(order_info, dominos))

    component.add_entities(hass.data[DOMAIN]['entities'])

    # Return boolean to indicate that initialization was successfully.
    return True


class Dominos():

    def __init__(self, hass, config):
        self.hass = hass
        self.customer = Customer(
            config[DOMAIN].get(ATTR_FIRST_NAME),
            config[DOMAIN].get(ATTR_LAST_NAME),
            config[DOMAIN].get(ATTR_EMAIL),
            config[DOMAIN].get(ATTR_PHONE),
            config[DOMAIN].get(ATTR_ADDRESS))
        self.address = Address(
            *self.customer.address.split(','),
            country=config[DOMAIN].get(ATTR_COUNTRY))
        self.country = config[DOMAIN].get(ATTR_COUNTRY)
        self._closest_store = False
        self._last_store_check = 0
        self.update_closest_store()

    def handle_order(self, call=None):
        """Handle ordering pizza."""

        entity_ids = call.data.get(ATTR_ORDER_ENTITY, None)

        target_orders = [order for order in self.hass.data[DOMAIN]['entities']
                         if order.entity_id in entity_ids]

        for order in target_orders:
            order.place()

    def update_closest_store(self):

        cur_time = time.time()
        if self._last_store_check + MIN_TIME_BETWEEN_STORE_UPDATES < cur_time:
            self._last_store_check = cur_time
            try:
                self._closest_store = self.address.closest_store()
            except Exception:
                self._closest_store = False

    @property
    def closest_store(self):
        return self._closest_store

    def dump_menu(self, hass):

        store = self._closest_store
        menu = store.get_menu()
        for product in menu.products:
            if isinstance(product.menu_data['Variants'], list):
                variants = ', '.join(product.menu_data['Variants'])
            else:
                variants = product.menu_data['Variants']

            message = 'name: ' + product.name + ' variants: ' + variants

            # We get some weird product names sometimes,
            # so clobber this to make it logger safe
            _LOGGER.warning(
                unicodedata.normalize('NFKC', message)
                .encode('ascii', 'ignore').decode('ascii'))


class DominosOrder(Entity):

    def __init__(self, order_info, dominos):
        self._name = order_info['name']
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, self._name, hass=dominos.hass)

        self._product_codes = order_info['codes']
        self._orderable = False
        self.dominos = dominos

    @property
    def name(self):
        return self._name

    @property
    def product_codes(self):
        return self._product_codes

    @property
    def orderable(self):
        return self._orderable

    @property
    def state(self):

        if self.dominos.closest_store is False:
            return 'closed'
        else:
            return 'orderable' if self._orderable else 'unorderable'

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):

        try:
            self.dominos.update_closest_store()
        except Exception:
            self._orderable = False
            return

        try:
            order = self.order()
            order.pay_with()
            self._orderable = True
        except Exception:
            self._orderable = False

    def order(self):
        order = Order(
            self.dominos.closest_store,
            self.dominos.customer,
            self.dominos.address,
            self.dominos.country)

        for code in self._product_codes:
            order.add_item(code)

        return order

    def place(self):
        try:
            order = self.order()
            order.place()
        except Exception:
            self._orderable = False
            _LOGGER.warning(
                'Attempted to order Dominos - Order invalid or store closed')

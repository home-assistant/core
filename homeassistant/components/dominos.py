"""
Support for Dominos Pizza ordering.

The Dominos Pizza component ceates a service which can be invoked to order
from their menu

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/dominos/.
"""
import asyncio
import logging
import time
import unicodedata
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components import http
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity, async_generate_entity_id
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
ATTR_SHOW_MENU = 'show_menu'
ATTR_ORDER_ENTITY = 'order_entity_id'
ATTR_ORDER_NAME = 'name'
ATTR_ORDER_CODES = 'codes'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)
MIN_TIME_BETWEEN_STORE_UPDATES = 1800

REQUIREMENTS = ['pizzapi==0.0.2']

DEPENDENCIES = ['http']

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
        vol.Optional(ATTR_SHOW_MENU): cv.boolean,
        vol.Optional(ATTR_ORDERS): vol.All(cv.ensure_list, [_ORDERS_SCHEMA]),
    }),
}, extra=vol.ALLOW_EXTRA)

# pylint: disable=broad-except


@asyncio.coroutine
def async_setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""
    dominos = Dominos(hass, config)

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    hass.data[DOMAIN] = {}
    entities = []

    hass.services.async_register(DOMAIN, 'order', dominos.handle_order)

    if config[DOMAIN].get(ATTR_DUMP_MENU):
        yield from dominos.dump_menu(hass)
        hass.http.register_view(DominosProductListView)
        yield from hass.components.frontend.async_register_built_in_panel(
            'dominos', 'dominos', 'mdi:pizza')

    for order_info in config[DOMAIN].get(ATTR_ORDERS):
        order = DominosOrder(order_info, dominos)
        entities.append(order)

    yield from component.async_add_entities(entities)

    # Return boolean to indicate that initialization was successfully.
    return True


class Dominos():
    """Main Dominos service."""

    def __init__(self, hass, config):
        """Set up main service."""
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
        """Update the shared closest store (if open)."""
        cur_time = time.time()
        if self._last_store_check + MIN_TIME_BETWEEN_STORE_UPDATES < cur_time:
            self._last_store_check = cur_time
            try:
                self._closest_store = self.address.closest_store()
            except Exception:
                self._closest_store = False

    @property
    def closest_store(self):
        """Return the shared closest store (or False if all closed)."""
        return self._closest_store

    @asyncio.coroutine
    def dump_menu(self, hass):
        """Dump the closest stores menu into the logs."""

        if self._closest_store is False:
            _LOGGER.warning('Cannot get menu. Store may be closed')
            return

        menu = self._closest_store.get_menu()
        hass.data[DOMAIN]['products'] = []

        for product in menu.products:
            item = {}
            if isinstance(product.menu_data['Variants'], list):
                variants = ', '.join(product.menu_data['Variants'])
            else:
                variants = product.menu_data['Variants']
            item['name'] = product.name
            item['variants'] = variants
            hass.data[DOMAIN]['products'].append(item)


class DominosProductListView(http.HomeAssistantView):
    """View to retrieve product list content."""

    url = '/api/dominos'
    name = "api:dominos"

    @callback
    def get(self, request):
        """Retrieve if API is running."""
        hass = request.app['hass']

        return self.json(request.app['hass'].data[DOMAIN]['products'])


class DominosOrder(Entity):
    """Represents a Dominos order entity."""

    def __init__(self, order_info, dominos):
        """Set up the entity."""
        self._name = order_info['name']
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, self._name, hass=dominos.hass)

        self._product_codes = order_info['codes']
        self._orderable = False
        self.dominos = dominos

    @property
    def name(self):
        """Return the orders name."""
        return self._name

    @property
    def product_codes(self):
        """Return the orders product codes."""
        return self._product_codes

    @property
    def orderable(self):
        """Return the true if orderable."""
        return self._orderable

    @property
    def state(self):
        """Return the state either closed, orderable or unorderable."""
        if self.dominos.closest_store is False:
            return 'closed'
        else:
            return 'orderable' if self._orderable else 'unorderable'

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update the order state and refreshes the store."""
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
        """Create the order object."""
        order = Order(
            self.dominos.closest_store,
            self.dominos.customer,
            self.dominos.address,
            self.dominos.country)

        for code in self._product_codes:
            order.add_item(code)

        return order

    def place(self):
        """Place the order."""
        try:
            order = self.order()
            order.place()
        except Exception:
            self._orderable = False
            _LOGGER.warning(
                'Attempted to order Dominos - Order invalid or store closed')

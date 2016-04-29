"""
Support for the Uber API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.uber/
"""
import logging
from datetime import timedelta

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['uber_rides==0.2.1']

ICON = 'mdi:taxi'

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Uber sensor."""
    if None in (config.get('start_latitude'), config.get('start_longitude')):
        _LOGGER.error(
            "You must set start latitude and longitude to use the Uber sensor!"
        )
        return False

    if config.get('server_token') is None:
        _LOGGER.error("You must set a server_token to use the Uber sensor!")
        return False

    from uber_rides.session import Session

    session = Session(server_token=config.get('server_token'))

    wanted_product_ids = config.get('product_ids')

    dev = []
    timeandpriceest = UberEstimate(session, config['start_latitude'],
                                   config['start_longitude'],
                                   config.get('end_latitude'),
                                   config.get('end_longitude'))
    for product_id, product in timeandpriceest.products.items():
        if (wanted_product_ids is not None) and \
           (product_id not in wanted_product_ids):
            continue
        dev.append(UberSensor('time', timeandpriceest, product_id, product))
        is_metered = (product['price_details']['estimate'] == "Metered")
        if 'price_details' in product and is_metered is False:
            dev.append(UberSensor('price', timeandpriceest,
                                  product_id, product))
    add_devices(dev)


# pylint: disable=too-few-public-methods
class UberSensor(Entity):
    """Implementation of an Uber sensor."""

    def __init__(self, sensorType, products, product_id, product):
        """Initialize the Uber sensor."""
        self.data = products
        self._product_id = product_id
        self._product = product
        self._sensortype = sensorType
        self._name = "{} {}".format(self._product['display_name'],
                                    self._sensortype)
        if self._sensortype == "time":
            self._unit_of_measurement = "min"
            time_estimate = self._product.get('time_estimate_seconds', 0)
            self._state = int(time_estimate / 60)
        elif self._sensortype == "price":
            if 'price_details' in self._product:
                price_details = self._product['price_details']
                self._unit_of_measurement = price_details.get('currency_code',
                                                              'N/A')
                if 'low_estimate' in price_details:
                    statekey = 'minimum'
                else:
                    statekey = 'low_estimate'
                self._state = int(price_details.get(statekey, 0))
            else:
                self._unit_of_measurement = 'N/A'
                self._state = 0
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        time_estimate = self._product.get('time_estimate_seconds', 'N/A')
        params = {
            'Product ID': self._product['product_id'],
            'Product short description': self._product['short_description'],
            'Product display name': self._product['display_name'],
            'Product description': self._product['description'],
            'Pickup time estimate (in seconds)': time_estimate,
            'Trip duration (in seconds)': self._product.get('duration', 'N/A'),
            'Vehicle Capacity': self._product['capacity']
        }

        if 'price_details' in self._product:
            price_details = self._product['price_details']
            distance_key = 'Trip distance (in {}s)'.format(price_details[
                'distance_unit'])
            distance_val = self._product.get('distance')
            params['Minimum price'] = price_details['minimum'],
            params['Cost per minute'] = price_details['cost_per_minute'],
            params['Distance units'] = price_details['distance_unit'],
            params['Cancellation fee'] = price_details['cancellation_fee'],
            params['Cost per distance'] = price_details['cost_per_distance'],
            params['Base price'] = price_details['base'],
            params['Price estimate'] = price_details.get('estimate', 'N/A'),
            params['Price currency code'] = price_details.get('currency_code'),
            params['High price estimate'] = price_details.get('high_estimate',
                                                              'N/A'),
            params['Low price estimate'] = price_details.get('low_estimate',
                                                             'N/A'),
            params['Surge multiplier'] = price_details.get('surge_multiplier',
                                                           'N/A')
        else:
            distance_key = 'Trip distance (in miles)'
            distance_val = self._product.get('distance', 'N/A')

        params[distance_key] = distance_val

        return params

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    # pylint: disable=too-many-branches
    def update(self):
        """Get the latest data from the Uber API and update the states."""
        self.data.update()
        self._product = self.data.products[self._product_id]
        if self._sensortype == "time":
            time_estimate = self._product.get('time_estimate_seconds', 0)
            self._state = int(time_estimate / 60)
        elif self._sensortype == "price":
            price_details = self._product.get('price_details')
            if price_details is not None:
                min_price = price_details.get('minimum')
                self._state = int(price_details.get('low_estimate', min_price))
            else:
                self._state = 0


# pylint: disable=too-few-public-methods
class UberEstimate(object):
    """The class for handling the time and price estimate."""

    # pylint: disable=too-many-arguments
    def __init__(self, session, start_latitude, start_longitude,
                 end_latitude=None, end_longitude=None):
        """Initialize the UberEstimate object."""
        self._session = session
        self.start_latitude = start_latitude
        self.start_longitude = start_longitude
        self.end_latitude = end_latitude
        self.end_longitude = end_longitude
        self.products = None
        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest product info and estimates from the Uber API."""
        from uber_rides.client import UberRidesClient
        client = UberRidesClient(self._session)

        self.products = {}

        products_response = client.get_products(
            self.start_latitude, self.start_longitude)

        products = products_response.json.get('products')

        for product in products:
            self.products[product['product_id']] = product

        if self.end_latitude is not None and self.end_longitude is not None:
            price_response = client.get_price_estimates(
                self.start_latitude,
                self.start_longitude,
                self.end_latitude,
                self.end_longitude)

            prices = price_response.json.get('prices', [])

            for price in prices:
                product = self.products[price['product_id']]
                price_details = product.get("price_details")
                product["duration"] = price.get('duration', '0')
                product["distance"] = price.get('distance', '0')
                if price_details is not None:
                    price_details["estimate"] = price.get('estimate',
                                                          '0')
                    price_details["high_estimate"] = price.get('high_estimate',
                                                               '0')
                    price_details["low_estimate"] = price.get('low_estimate',
                                                              '0')
                    surge_multiplier = price.get('surge_multiplier', '0')
                    price_details["surge_multiplier"] = surge_multiplier

        estimate_response = client.get_pickup_time_estimates(
            self.start_latitude, self.start_longitude)

        estimates = estimate_response.json.get('times')

        for estimate in estimates:
            self.products[estimate['product_id']][
                "time_estimate_seconds"] = estimate.get('estimate', '0')

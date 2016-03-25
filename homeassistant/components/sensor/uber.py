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
REQUIREMENTS = ['https://github.com/denismakogon/rides-python-sdk/archive/'
                'py3-support.zip#'
                'uber_rides==0.1.2-dev']

ICON = 'mdi:taxi'

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)


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
    start_lat_long = LatLong(config.get('start_latitude'),
                             config.get('start_longitude'))
    end_lat_long = LatLong(config.get('end_latitude'),
                           config.get('end_longitude'))
    timeandpriceest = UberEstimate(session, start_lat_long, end_lat_long)
    for product_id, product in timeandpriceest.products.items():
        if wanted_product_ids is not None and product_id in wanted_product_ids:
            dev.append(UberSensor('time',
                                  timeandpriceest,
                                  product_id, product))
            dev.append(UberSensor('price',
                                  timeandpriceest,
                                  product_id, product))
        elif wanted_product_ids is None:
            dev.append(UberSensor('time',
                                  timeandpriceest,
                                  product_id,
                                  product))
            dev.append(UberSensor('price',
                                  timeandpriceest,
                                  product_id,
                                  product))
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
        self._name = self._product.get('display_name') + " " + self._sensortype
        if self._sensortype == "time":
            self._unit_of_measurement = "min"
            self._state = int(self._product.get(
                'time_estimate_seconds', 0
            ) / 60)
        elif self._sensortype == "price":
            if self._product.get('price_details').get('low_estimate') is None:
                self._unit_of_measurement = self._product.get(
                    'price_details'
                ).get(
                    'currency_code'
                )
                self._state = int(self._product.get(
                    'price_details'
                ).get(
                    'minimum'
                ))
            else:
                self._unit_of_measurement = self._product.get(
                    'price_details').get('currency_code')
                self._state = int(
                    self._product.get('price_details').get('low_estimate'))
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
        distance_key = 'Trip distance (in '+self._product.get(
            'price_details').get('distance_unit')+'s)'
        distance_val = self._product.get('distance')
        if self._product.get(
                'price_details'
        ).get(
            'distance_unit'
        ) is None or self._product.get(
            'distance'
        ) is None:
            distance_key = 'Trip distance'
            distance_val = 'N/A'
        return {
            'Product ID': self._product.get('product_id'),
            'Product short description': self._product.get(
                'short_description'),
            'Product display name': self._product.get('display_name'),
            'Product description': self._product.get('description'),
            'Pickup time estimate (in seconds)':
            self._product.get('time_estimate_seconds'),
            'Trip duration (in seconds)': self._product.get('duration', 'N/A'),
            distance_key: distance_val,
            'Vehicle Capacity': self._product.get('capacity'),
            'Minimum price': self._product.get('price_details').get('minimum'),
            'Cost per minute': self._product.get(
                'price_details').get('cost_per_minute'),
            'Distance units': self._product.get(
                'price_details').get('distance_unit'),
            'Cancellation fee': self._product.get(
                'price_details').get('cancellation_fee'),
            'Cost per distance unit': self._product.get(
                'price_details').get('cost_per_distance'),
            'Base price': self._product.get('price_details').get('base'),
            'Price estimate': self._product.get(
                'price_details').get('estimate', 'N/A'),
            'Price currency code': self._product.get(
                'price_details').get('currency_code'),
            'High price estimate': self._product.get(
                'price_details').get('high_estimate', 'N/A'),
            'Low price estimate': self._product.get(
                'price_details').get('low_estimate', 'N/A'),
            'Surge multiplier': self._product.get(
                'price_details').get('surge_multiplier', 'N/A')
        }

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    # pylint: disable=too-many-branches
    def update(self):
        """Get the latest data from the Uber API and update the states."""
        self.data.update()
        self._product = self.data.products[self._product_id]


class LatLong(object):
    """A container for a latitude and longitude pair."""

    def __init__(self, latitude, longitude):
        """Initialize the LatLong object."""
        self.latitude = latitude
        self.longitude = longitude


# pylint: disable=too-few-public-methods
class UberEstimate(object):
    """The class for handling the time and price estimate."""

    def __init__(self, session, start_latlong, end_latlong=None):
        """Initialize the UberEstimate object."""
        self._session = session
        self.start_latitude = start_latlong.latitude
        self.start_longitude = start_latlong.longitude
        self.end_latitude = end_latlong.latitude
        self.end_longitude = end_latlong.longitude
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
            self.products[product.get('product_id')] = product

        if self.end_latitude is not None and self.end_longitude is not None:
            price_response = client.get_price_estimates(
                self.start_latitude,
                self.start_longitude,
                self.end_latitude,
                self.end_longitude)

            prices = price_response.json.get('prices')

            for price in prices:
                self.products[price.get('product_id')][
                    "duration"] = price.get('duration')
                self.products[price.get('product_id')][
                    "distance"] = price.get('distance')
                self.products[price.get('product_id')]["price_details"][
                    "estimate"] = price.get('estimate')
                self.products[price.get('product_id')]["price_details"][
                    "high_estimate"] = price.get('high_estimate')
                self.products[price.get('product_id')]["price_details"][
                    "low_estimate"] = price.get('low_estimate')
                self.products[price.get('product_id')]["price_details"][
                    "surge_multiplier"] = price.get('surge_multiplier')

        estimate_response = client.get_pickup_time_estimates(
            self.start_latitude, self.start_longitude)

        estimates = estimate_response.json.get('times')

        for estimate in estimates:
            self.products[estimate.get('product_id')][
                "time_estimate_seconds"] = estimate.get('estimate')

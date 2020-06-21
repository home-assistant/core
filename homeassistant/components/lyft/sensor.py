"""Support for the Lyft API."""
from datetime import timedelta
import logging

from lyft_rides.auth import ClientCredentialGrant
from lyft_rides.client import LyftRidesClient
from lyft_rides.errors import APIError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, TIME_MINUTES
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

CONF_END_LATITUDE = "end_latitude"
CONF_END_LONGITUDE = "end_longitude"
CONF_PRODUCT_IDS = "product_ids"
CONF_START_LATITUDE = "start_latitude"
CONF_START_LONGITUDE = "start_longitude"

ICON = "mdi:taxi"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Optional(CONF_START_LATITUDE): cv.latitude,
        vol.Optional(CONF_START_LONGITUDE): cv.longitude,
        vol.Optional(CONF_END_LATITUDE): cv.latitude,
        vol.Optional(CONF_END_LONGITUDE): cv.longitude,
        vol.Optional(CONF_PRODUCT_IDS): vol.All(cv.ensure_list, [cv.string]),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Lyft sensor."""

    auth_flow = ClientCredentialGrant(
        client_id=config.get(CONF_CLIENT_ID),
        client_secret=config.get(CONF_CLIENT_SECRET),
        scopes="public",
        is_sandbox_mode=False,
    )
    try:
        session = auth_flow.get_session()

        timeandpriceest = LyftEstimate(
            session,
            config.get(CONF_START_LATITUDE, hass.config.latitude),
            config.get(CONF_START_LONGITUDE, hass.config.longitude),
            config.get(CONF_END_LATITUDE),
            config.get(CONF_END_LONGITUDE),
        )
        timeandpriceest.fetch_data()
    except APIError as exc:
        _LOGGER.error("Error setting up Lyft platform: %s", exc)
        return False

    wanted_product_ids = config.get(CONF_PRODUCT_IDS)

    dev = []
    for product_id, product in timeandpriceest.products.items():
        if (wanted_product_ids is not None) and (product_id not in wanted_product_ids):
            continue
        dev.append(LyftSensor("time", timeandpriceest, product_id, product))
        if product.get("estimate") is not None:
            dev.append(LyftSensor("price", timeandpriceest, product_id, product))
    add_entities(dev, True)


class LyftSensor(Entity):
    """Implementation of an Lyft sensor."""

    def __init__(self, sensorType, products, product_id, product):
        """Initialize the Lyft sensor."""
        self.data = products
        self._product_id = product_id
        self._product = product
        self._sensortype = sensorType
        self._name = f"{self._product['display_name']} {self._sensortype}"
        if "lyft" not in self._name.lower():
            self._name = f"Lyft{self._name}"
        if self._sensortype == "time":
            self._unit_of_measurement = TIME_MINUTES
        elif self._sensortype == "price":
            estimate = self._product["estimate"]
            if estimate is not None:
                self._unit_of_measurement = estimate.get("currency")
        self._state = None

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
        params = {
            "Product ID": self._product["ride_type"],
            "Product display name": self._product["display_name"],
            "Vehicle Capacity": self._product["seats"],
        }

        if self._product.get("pricing_details") is not None:
            pricing_details = self._product["pricing_details"]
            params["Base price"] = pricing_details.get("base_charge")
            params["Cancellation fee"] = pricing_details.get("cancel_penalty_amount")
            params["Minimum price"] = pricing_details.get("cost_minimum")
            params["Cost per mile"] = pricing_details.get("cost_per_mile")
            params["Cost per minute"] = pricing_details.get("cost_per_minute")
            params["Price currency code"] = pricing_details.get("currency")
            params["Service fee"] = pricing_details.get("trust_and_service")

        if self._product.get("estimate") is not None:
            estimate = self._product["estimate"]
            params["Trip distance (in miles)"] = estimate.get(
                "estimated_distance_miles"
            )
            params["High price estimate (in cents)"] = estimate.get(
                "estimated_cost_cents_max"
            )
            params["Low price estimate (in cents)"] = estimate.get(
                "estimated_cost_cents_min"
            )
            params["Trip duration (in seconds)"] = estimate.get(
                "estimated_duration_seconds"
            )

            params["Prime Time percentage"] = estimate.get("primetime_percentage")

        if self._product.get("eta") is not None:
            eta = self._product["eta"]
            params["Pickup time estimate (in seconds)"] = eta.get("eta_seconds")

        return {k: v for k, v in params.items() if v is not None}

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the latest data from the Lyft API and update the states."""
        self.data.update()
        try:
            self._product = self.data.products[self._product_id]
        except KeyError:
            return
        self._state = None
        if self._sensortype == "time":
            eta = self._product["eta"]
            if (eta is not None) and (eta.get("is_valid_estimate")):
                time_estimate = eta.get("eta_seconds")
                if time_estimate is None:
                    return
                self._state = int(time_estimate / 60)
        elif self._sensortype == "price":
            estimate = self._product["estimate"]
            if (estimate is not None) and estimate.get("is_valid_estimate"):
                self._state = (
                    int(
                        (
                            estimate.get("estimated_cost_cents_min", 0)
                            + estimate.get("estimated_cost_cents_max", 0)
                        )
                        / 2
                    )
                    / 100
                )


class LyftEstimate:
    """The class for handling the time and price estimate."""

    def __init__(
        self,
        session,
        start_latitude,
        start_longitude,
        end_latitude=None,
        end_longitude=None,
    ):
        """Initialize the LyftEstimate object."""
        self._session = session
        self.start_latitude = start_latitude
        self.start_longitude = start_longitude
        self.end_latitude = end_latitude
        self.end_longitude = end_longitude
        self.products = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest product info and estimates from the Lyft API."""

        try:
            self.fetch_data()
        except APIError as exc:
            _LOGGER.error("Error fetching Lyft data: %s", exc)

    def fetch_data(self):
        """Get the latest product info and estimates from the Lyft API."""

        client = LyftRidesClient(self._session)

        self.products = {}

        products_response = client.get_ride_types(
            self.start_latitude, self.start_longitude
        )

        products = products_response.json.get("ride_types")

        for product in products:
            self.products[product["ride_type"]] = product

        if self.end_latitude is not None and self.end_longitude is not None:
            price_response = client.get_cost_estimates(
                self.start_latitude,
                self.start_longitude,
                self.end_latitude,
                self.end_longitude,
            )

            prices = price_response.json.get("cost_estimates", [])

            for price in prices:
                product = self.products[price["ride_type"]]
                if price.get("is_valid_estimate"):
                    product["estimate"] = price

        eta_response = client.get_pickup_time_estimates(
            self.start_latitude, self.start_longitude
        )

        etas = eta_response.json.get("eta_estimates")

        for eta in etas:
            if eta.get("is_valid_estimate"):
                self.products[eta["ride_type"]]["eta"] = eta

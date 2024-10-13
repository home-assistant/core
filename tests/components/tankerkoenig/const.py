"""Constants for the Tankerkoenig tests."""

from aiotankerkoenig import PriceInfo, Station, Status

from homeassistant.components.tankerkoenig.const import CONF_FUEL_TYPES, CONF_STATIONS
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
)

NEARBY_STATIONS = [
    Station(
        id="3bcd61da-xxxx-xxxx-xxxx-19d5523a7ae8",
        brand="BrandA",
        place="CityA",
        street="Main",
        house_number="1",
        distance=1,
        lat=51.1,
        lng=13.1,
        name="Station ABC",
        post_code=1234,
    ),
    Station(
        id="36b4b812-xxxx-xxxx-xxxx-c51735325858",
        brand="BrandB",
        place="CityB",
        street="School",
        house_number="2",
        distance=2,
        lat=51.2,
        lng=13.2,
        name="Station DEF",
        post_code=2345,
    ),
]

STATION = Station(
    id="3bcd61da-xxxx-xxxx-xxxx-19d5523a7ae8",
    name="Station ABC",
    brand="Station",
    street="Somewhere Street",
    house_number="1",
    post_code=1234,
    place="Somewhere",
    opening_times=[],
    overrides=[],
    whole_day=True,
    is_open=True,
    e5=1.719,
    e10=1.659,
    diesel=1.659,
    lat=51.1,
    lng=13.1,
    state="xxXX",
)

STATION_MISSING_FUELTYPE = Station(
    id="3bcd61da-xxxx-xxxx-xxxx-19d5523a7ae8",
    name="Station ABC",
    brand="Station",
    street="Somewhere Street",
    house_number="1",
    post_code=1234,
    place="Somewhere",
    opening_times=[],
    overrides=[],
    whole_day=True,
    is_open=True,
    e5=1.719,
    e10=1.659,
    lat=51.1,
    lng=13.1,
    state="xxXX",
)

PRICES = {
    "3bcd61da-xxxx-xxxx-xxxx-19d5523a7ae8": PriceInfo(
        status=Status.OPEN,
        e5=1.719,
        e10=1.659,
        diesel=1.659,
    ),
}

PRICES_MISSING_FUELTYPE = {
    "3bcd61da-xxxx-xxxx-xxxx-19d5523a7ae8": PriceInfo(
        status=Status.OPEN,
        e5=1.719,
        e10=1.659,
    ),
}

CONFIG_DATA = {
    CONF_NAME: "Home",
    CONF_API_KEY: "269534f6-xxxx-xxxx-xxxx-yyyyzzzzxxxx",
    CONF_FUEL_TYPES: ["e5"],
    CONF_LOCATION: {CONF_LATITUDE: 51.0, CONF_LONGITUDE: 13.0},
    CONF_RADIUS: 2.0,
    CONF_STATIONS: [
        "3bcd61da-xxxx-xxxx-xxxx-19d5523a7ae8",
    ],
}

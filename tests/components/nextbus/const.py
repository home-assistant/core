"""Constants for NextBus tests."""

from homeassistant.components.nextbus.const import CONF_AGENCY, CONF_ROUTE, DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_STOP

VALID_AGENCY = "sfmta-cis"
VALID_ROUTE = "F"
VALID_STOP = "5184"
VALID_COORDINATOR_KEY = f"{VALID_AGENCY}-{VALID_STOP}"
VALID_AGENCY_TITLE = "San Francisco Muni"
VALID_ROUTE_TITLE = "F-Market & Wharves"
VALID_STOP_TITLE = "Market St & 7th St"
SENSOR_ID = "sensor.san_francisco_muni_f_market_wharves_market_st_7th_st"

ROUTE_2 = "G"
ROUTE_TITLE_2 = "G-Market & Wharves"
SENSOR_ID_2 = "sensor.san_francisco_muni_g_market_wharves_market_st_7th_st"

PLATFORM_CONFIG = {
    SENSOR_DOMAIN: {
        "platform": DOMAIN,
        CONF_AGENCY: VALID_AGENCY,
        CONF_ROUTE: VALID_ROUTE,
        CONF_STOP: VALID_STOP,
    },
}


CONFIG_BASIC = {
    DOMAIN: {
        CONF_AGENCY: VALID_AGENCY,
        CONF_ROUTE: VALID_ROUTE,
        CONF_STOP: VALID_STOP,
    }
}

CONFIG_BASIC_2 = {
    DOMAIN: {
        CONF_AGENCY: VALID_AGENCY,
        CONF_ROUTE: ROUTE_2,
        CONF_STOP: VALID_STOP,
    }
}

BASIC_RESULTS = [
    {
        "route": {
            "title": VALID_ROUTE_TITLE,
            "id": VALID_ROUTE,
        },
        "stop": {
            "name": VALID_STOP_TITLE,
            "id": VALID_STOP,
        },
        "values": [
            {"minutes": 1, "timestamp": 1553807371000},
            {"minutes": 2, "timestamp": 1553807372000},
            {"minutes": 3, "timestamp": 1553807373000},
            {"minutes": 10, "timestamp": 1553807380000},
        ],
    },
    {
        "route": {
            "title": ROUTE_TITLE_2,
            "id": ROUTE_2,
        },
        "stop": {
            "name": VALID_STOP_TITLE,
            "id": VALID_STOP,
        },
        "values": [
            {"minutes": 90, "timestamp": 1553807379000},
        ],
    },
]

NO_UPCOMING = [
    {
        "route": {
            "title": VALID_ROUTE_TITLE,
            "id": VALID_ROUTE,
        },
        "stop": {
            "name": VALID_STOP_TITLE,
            "id": VALID_STOP,
        },
        "values": [],
    },
    {
        "route": {
            "title": ROUTE_TITLE_2,
            "id": ROUTE_2,
        },
        "stop": {
            "name": VALID_STOP_TITLE,
            "id": VALID_STOP,
        },
        "values": [],
    },
]

"""Constants for the London Air integration."""

from datetime import timedelta

import aiohttp

DOMAIN = "london_air"

CONF_LOCATIONS = "locations"

URL = "https://api.erg.ic.ac.uk/AirQuality/Hourly/MonitoringIndex/GroupName=London/Json"

SCAN_INTERVAL = timedelta(minutes=30)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)

MANUFACTURER = "Imperial College London"

AUTHORITIES = [
    "Barking and Dagenham",
    "Barnet",
    "Bexley",
    "Brent",
    "Bromley",
    "Camden",
    "City of London",
    "Croydon",
    "Ealing",
    "Enfield",
    "Greenwich",
    "Hackney",
    "Hammersmith and Fulham",
    "Haringey",
    "Harrow",
    "Havering",
    "Hillingdon",
    "Hounslow",
    "Islington",
    "Kensington and Chelsea",
    "Kingston",
    "Lambeth",
    "Lewisham",
    "Merton",
    "Newham",
    "Redbridge",
    "Richmond",
    "Southwark",
    "Sutton",
    "Tower Hamlets",
    "Waltham Forest",
    "Wandsworth",
    "Westminster",
]

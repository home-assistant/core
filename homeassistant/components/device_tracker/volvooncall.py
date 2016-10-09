"""
Support for Volvo On Call.

http://www.volvocars.com/intl/own/owner-info/volvo-on-call
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.volvooncall/
"""
import logging
from datetime import timedelta
from urllib.parse import urljoin
import voluptuous as vol
import requests

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.util.dt import utcnow
from homeassistant.util import slugify
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME)
from homeassistant.components.device_tracker import (
    DEFAULT_SCAN_INTERVAL,
    PLATFORM_SCHEMA)

MIN_TIME_BETWEEN_SCANS = timedelta(minutes=1)

_LOGGER = logging.getLogger(__name__)

SERVICE_URL = 'https://vocapi.wirelesscar.net/customerapi/rest/v3.0/'
HEADERS = {"X-Device-Id": "Device",
           "X-OS-Type": "Android",
           "X-Originator-Type": "App"}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


def setup_scanner(hass, config, see):
    """Validate the configuration and return a scanner."""
    session = requests.Session()
    session.headers.update(HEADERS)
    session.auth = (config.get(CONF_USERNAME),
                    config.get(CONF_PASSWORD))

    interval = max(MIN_TIME_BETWEEN_SCANS.seconds,
                   config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

    def query(ref, rel=SERVICE_URL):
        """Perform a query to the online service."""
        url = urljoin(rel, ref)
        _LOGGER.debug("Request for %s", url)
        res = session.get(url, timeout=15)
        res.raise_for_status()
        _LOGGER.debug("Received %s", res.json())
        return res.json()

    def update(now):
        """Update status from the online service."""
        try:
            _LOGGER.debug("Updating")
            status = query("status", vehicle_url)
            position = query("position", vehicle_url)
            see(dev_id=dev_id,
                host_name=host_name,
                gps=(position["position"]["latitude"],
                     position["position"]["longitude"]),
                attributes=dict(
                    tank_volume=attributes["fuelTankVolume"],
                    washer_fluid=status["washerFluidLevel"],
                    brake_fluid=status["brakeFluid"],
                    service_warning=status["serviceWarningStatus"],
                    fuel=status["fuelAmount"],
                    odometer=status["odometer"],
                    range=status["distanceToEmpty"]))
        except requests.exceptions.RequestException as error:
            _LOGGER.error("Could not query server: %s", error)
        finally:
            track_point_in_utc_time(hass, update,
                                    now + timedelta(seconds=interval))

    try:
        _LOGGER.info('Logging in to service')
        user = query("customeraccounts")
        rel = query(user["accountVehicleRelations"][0])
        vehicle_url = rel["vehicle"] + '/'
        attributes = query("attributes", vehicle_url)

        dev_id = "volvo_" + slugify(attributes["registrationNumber"])
        host_name = "%s %s/%s" % (attributes["registrationNumber"],
                                  attributes["vehicleType"],
                                  attributes["modelYear"])
        update(utcnow())
        return True
    except requests.exceptions.RequestException as error:
        _LOGGER.error("Could not log in to service. "
                      "Please check configuration: "
                      "%s", error)
        return False

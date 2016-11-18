"""
Support for Volvo On Call.

http://www.volvocars.com/intl/own/owner-info/volvo-on-call
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.volvooncall/
"""
import logging
from datetime import timedelta
import voluptuous as vol

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

REQUIREMENTS = ['volvooncall==0.1.1']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


def setup_scanner(hass, config, see):
    """Validate the configuration and return a scanner."""
    from volvooncall import Connection
    connection = Connection(
        config.get(CONF_USERNAME),
        config.get(CONF_PASSWORD))

    interval = max(MIN_TIME_BETWEEN_SCANS.seconds,
                   config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

    def _see_vehicle(vehicle):
        position = vehicle["position"]
        dev_id = "volvo_" + slugify(vehicle["registrationNumber"])
        host_name = "%s (%s/%s)" % (
            vehicle["registrationNumber"],
            vehicle["vehicleType"],
            vehicle["modelYear"])

        def any_opened(door):
            """True if any door/window is opened."""
            return any([door[key] for key in door if "Open" in key])

        attributes = dict(
            unlocked=not vehicle["carLocked"],
            tank_volume=vehicle["fuelTankVolume"],
            average_fuel_consumption=round(
                vehicle["averageFuelConsumption"] / 10, 1),  # l/100km
            washer_fluid_low=vehicle["washerFluidLevel"] != "Normal",
            brake_fluid_low=vehicle["brakeFluid"] != "Normal",
            service_warning=vehicle["serviceWarningStatus"] != "Normal",
            bulb_failures=len(vehicle["bulbFailures"]) > 0,
            doors_open=any_opened(vehicle["doors"]),
            windows_open=any_opened(vehicle["windows"]),
            fuel=vehicle["fuelAmount"],
            odometer=round(vehicle["odometer"] / 1000),  # km
            range=vehicle["distanceToEmpty"])

        if "heater" in vehicle and \
           "status" in vehicle["heater"]:
            attributes.update(heater_on=vehicle["heater"]["status"] != "off")

        see(dev_id=dev_id,
            host_name=host_name,
            gps=(position["latitude"],
                 position["longitude"]),
            attributes=attributes)

    def update(now):
        """Update status from the online service."""
        _LOGGER.info("Updating")
        try:
            res, vehicles = connection.update()
            if not res:
                _LOGGER.error("Could not query server")
                return False

            for vehicle in vehicles:
                _see_vehicle(vehicle)

            return True
        finally:
            track_point_in_utc_time(hass, update,
                                    now + timedelta(seconds=interval))

    _LOGGER.info('Logging in to service')
    return update(utcnow())

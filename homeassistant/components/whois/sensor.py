"""Get WHOIS information for a given host."""
from datetime import timedelta
import logging

import voluptuous as vol
import whois

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_DOMAIN, CONF_NAME, TIME_DAYS
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Whois"

ATTR_EXPIRES = "expires"
ATTR_NAME_SERVERS = "name_servers"
ATTR_REGISTRAR = "registrar"
ATTR_UPDATED = "updated"

SCAN_INTERVAL = timedelta(hours=24)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DOMAIN): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the WHOIS sensor."""
    domain = config.get(CONF_DOMAIN)
    name = config.get(CONF_NAME)

    try:
        if "expiration_date" in whois.whois(domain):
            add_entities([WhoisSensor(name, domain)], True)
        else:
            _LOGGER.error(
                "WHOIS lookup for %s didn't contain an expiration date", domain
            )
            return
    except whois.BaseException as ex:  # pylint: disable=broad-except
        _LOGGER.error("Exception %s occurred during WHOIS lookup for %s", ex, domain)
        return


class WhoisSensor(SensorEntity):
    """Implementation of a WHOIS sensor."""

    _attr_icon = "mdi:calendar-clock"
    _attr_native_unit_of_measurement = TIME_DAYS

    def __init__(self, name, domain):
        """Initialize the sensor."""
        self.whois = whois.whois
        self._domain = domain
        self._attr_name = name

    def _empty_value_and_attributes(self):
        """Empty the state and attributes on an error."""
        self._attr_native_value = None
        self._attr_extra_state_attributes = None

    def update(self):
        """Get the current WHOIS data for the domain."""
        try:
            response = self.whois(self._domain)
        except whois.BaseException as ex:  # pylint: disable=broad-except
            _LOGGER.error("Exception %s occurred during WHOIS lookup", ex)
            self._empty_value_and_attributes()
            return

        if response:
            if "expiration_date" not in response:
                _LOGGER.error(
                    "Failed to find expiration_date in whois lookup response. "
                    "Did find: %s",
                    ", ".join(response.keys()),
                )
                self._empty_value_and_attributes()
                return

            if not response["expiration_date"]:
                _LOGGER.error("Whois response contains empty expiration_date")
                self._empty_value_and_attributes()
                return

            attrs = {}

            expiration_date = response["expiration_date"]
            if isinstance(expiration_date, list):
                attrs[ATTR_EXPIRES] = expiration_date[0].isoformat()
                expiration_date = expiration_date[0]
            else:
                attrs[ATTR_EXPIRES] = expiration_date.isoformat()

            if "nameservers" in response:
                attrs[ATTR_NAME_SERVERS] = " ".join(response["nameservers"])

            if "updated_date" in response:
                update_date = response["updated_date"]
                if isinstance(update_date, list):
                    attrs[ATTR_UPDATED] = update_date[0].isoformat()
                else:
                    attrs[ATTR_UPDATED] = update_date.isoformat()

            if "registrar" in response:
                attrs[ATTR_REGISTRAR] = response["registrar"]

            time_delta = expiration_date - expiration_date.now()

            self._attr_extra_state_attributes = attrs
            self._attr_native_value = time_delta.days

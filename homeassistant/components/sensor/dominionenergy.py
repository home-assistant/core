"""
Support for Washington Dominion Energy.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.dominion_energy/
"""

import logging
from datetime import timedelta
import voluptuous as vol

from homeassistant.util import Throttle
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_PASSWORD, CONF_USERNAME)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


HOURS_TO_UPDATE = timedelta(hours=24)
CURRENT_BILL_SELECTOR = str("#homepageContent > div:nth-child(3) >"
                            " div:nth-child(2) > p > span")
REQUIREMENTS = ['selenium==3.11.0']

DEFAULT_NAME = "Dominion Energy"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setting the platform in HASS and getting the username and password."""
    from selenium import webdriver
    from selenium.common.exceptions import NoSuchElementException

    add_devices([DominionEnergySensor(config[CONF_NAME], config[CONF_USERNAME],
                                      config[CONF_PASSWORD])])
    try:
        driver = webdriver.PhantomJS()
        driver.set_window_size(1120, 550)
        driver.get("https://www.dominionenergy.com/sign-in")
        driver.find_element_by_id('user').send_keys(config[CONF_USERNAME])
        driver.find_element_by_id('password').send_keys(config[CONF_PASSWORD])
        driver.find_element_by_id('SignIn').click()
        driver.implicitly_wait(1)
        driver.find_element_by_css_selector(
            CURRENT_BILL_SELECTOR)
    except NoSuchElementException:
        _LOGGER.error("Setup DominionEnergy Fail"
                      " check if your username/password changed")
        return
    return


class DominionEnergySensor(Entity):
    """Washington Dominion Energy Sensor will check the bill on daily basis."""

    def __init__(self, name, username, password):
        """Initialize the sensor."""
        self._state = None
        self._password = password
        self._username = username
        self._name = name

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Returning the State of DominionEnergy Sensor."""
        return self._state

    @Throttle(HOURS_TO_UPDATE)
    def update(self):
        """Using Selenium to access Dominion website and fetch data."""
        from selenium import webdriver
        from selenium.common.exceptions import NoSuchElementException
        try:
            driver = webdriver.PhantomJS()
            driver.set_window_size(1120, 550)
            driver.get("https://www.dominionenergy.com/sign-in")
            driver.find_element_by_id('user').send_keys(self._username)
            driver.find_element_by_id('password').send_keys(self._password)
            driver.find_element_by_id('SignIn').click()
            driver.implicitly_wait(1)
            self._state = str(driver.find_element_by_css_selector(
                CURRENT_BILL_SELECTOR).text)
        except NoSuchElementException:
            _LOGGER.error("Update Dominion Energy Failed."
                          " check if your password changed")

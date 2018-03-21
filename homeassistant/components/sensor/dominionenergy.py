"""
Support for Washington Dominion Energy
website : dominionenergy.com

"""

from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity


def setup_platform(hass, config, add_devices, discovery_info=None):
    """setting the platform in HASS and getting the username
      and password from the config file"""
    add_devices([DominionEnergySensor(config['username'], config['password'])])


class DominionEnergySensor(Entity):
    """Washington Dominion Energy Sensor will check the bill
     if it's update on daily basis """
    from datetime import timedelta
    HOURS_TO_UPDATE = timedelta(hours=24)
    CURRENT_BILL_SELECTOR = "#homepageContent > div:nth-child(3) > div:nth-child(2) > p > span"

    def __init__(self, username, password):
        """Initialize the sensor."""
        self._state = None
        self._password = password
        self._username = username

    @property
    def name(self):
        return "Dominion Energy"

    @property
    def state(self):
        return self._state

    @Throttle(HOURS_TO_UPDATE)
    def update(self):
        from selenium import webdriver
        driver = webdriver.PhantomJS()
        driver.set_window_size(1120, 550)
        driver.get("https://www.dominionenergy.com/sign-in")
        driver.find_element_by_id('user').send_keys(self._username)
        driver.find_element_by_id('password').send_keys(self._password)
        driver.find_element_by_id('SignIn').click()
        driver.implicitly_wait(1)
        state = str(driver.find_element_by_css_selector(self.CURRENT_BILL_SELECTOR).text)
        self._state = state

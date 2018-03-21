"""Support for Washington Dominion Energy."""

from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity


def setup_platform(hass, config, add_devices, discovery_info=None):

    """Setting the platform in HASS and getting the username and password."""
    add_devices([DominionEnergySensor(config['username'], config['password'])])


class DominionEnergySensor(Entity):
    """Washington Dominion Energy Sensor will check the bill on daily basis."""

    from datetime import timedelta
    HOURS_TO_UPDATE = timedelta(hours=24)
    CURRENT_BILL_SELECTOR = str("#homepageContent > div:nth-child(3) >"
    +" div:nth-child(2) > p > span")

    def __init__(self, username, password):
        """Initialize the sensor."""
        self._state = None
        self._password = password
        self._username = username

    @property
    def name(self):
        """Name of the Sensor: DominionEnergy Sensor."""
        return "Dominion Energy"

    @property
    def state(self):
        """Returning the State of DominionEnergy Sensor."""
        return self._state

    @Throttle(HOURS_TO_UPDATE)
    def update(self):
        """Using Selenium to access Dominion website and fetch data."""
        from selenium import webdriver
        driver = webdriver.PhantomJS()
        driver.set_window_size(1120, 550)
        driver.get("https://www.dominionenergy.com/sign-in")
        driver.find_element_by_id('user').send_keys(self._username)
        driver.find_element_by_id('password').send_keys(self._password)
        driver.find_element_by_id('SignIn').click()
        driver.implicitly_wait(1)
        state = str(driver.find_element_by_css_selector(
            self.CURRENT_BILL_SELECTOR).text)
        self._state = state

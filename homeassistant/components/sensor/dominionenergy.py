
from homeassistant.helpers.entity import Entity
from selenium import webdriver
from homeassistant.util import Throttle
from datetime import timedelta

def setup_platform(hass,config,add_devices,discovery_info=None):
	add_devices([DominionEnergySensor(config['username'],config['password'])])

class DominionEnergySensor(Entity):
    HOURS_TO_UPDATE=timedelta(hours=12)
  

    def __init__(self,username,password):
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

        driver = webdriver.PhantomJS()
        driver.set_window_size(1120, 550)
        driver.get("https://www.dominionenergy.com/sign-in")
        driver.find_element_by_id('user').send_keys(self._username)
        driver.find_element_by_id('password').send_keys(self._password)
        driver.find_element_by_id('SignIn').click()
        driver.implicitly_wait(1)
        state = str(driver.find_element_by_css_selector('#homepageContent > div:nth-child(3) > div:nth-child(2) > p > span').text)

        self._state=state

    
	
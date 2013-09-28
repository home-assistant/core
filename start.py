from ConfigParser import SafeConfigParser

from homeassistant import HomeAssistant

from homeassistant.actors import HueLightControl
from homeassistant.observers import TomatoDeviceScanner

config = SafeConfigParser()
config.read("home-assistant.conf")

tomato = TomatoDeviceScanner(config.get('tomato','host'), config.get('tomato','username'), 
							 config.get('tomato','password'), config.get('tomato','http_id'))


ha = HomeAssistant(config.get("common","latitude"), config.get("common","longitude"))

ha.setup_light_trigger(tomato, HueLightControl())

ha.setup_http_interface(config.get("common","api_password"))

ha.start()

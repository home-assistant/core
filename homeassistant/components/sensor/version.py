from homeassistant.const import MAJOR_VERSION, MINOR_VERSION, PATCH_VERSION
from homeassistant.helpers.entity import Entity

def setup_platform(hass, config, add_devices, discovery_info=None):
	add_devices([HAversion()])

class HAversion(Entity):
	def __init__(self):
		self._state = None

	@property
	def name(self):
		return 'HA Verssion'

	@property
	def state(self):
		return self._state

	def update(self):
		self._state = str(MAJOR_VERSION) + '.' + str(MINOR_VERSION) + '.' + str(PATCH_VERSION)
	

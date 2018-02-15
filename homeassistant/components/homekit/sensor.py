from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change

from homeassistant.components.homekit.const import (
    SERVICES_ACCESSORY_INFO, SERVICES_TEMPERATURE_SENSOR,
    CHAR_MODEL, CHAR_MANUFACTURER, CHAR_SERIAL_NUMBER,
    CHAR_CURRENT_TEMPERATURE, HOMEASSISTANT)

from pyhap.loader import get_serv_loader
from pyhap.accessory import Accessory, Category


class TemperatureSensor(Accessory):
    category = Category.SENSOR

    def __init__(self, hass, _LOGGER, entity_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._hass = hass
        self._LOGGER = _LOGGER
        self._entity_id = entity_id

        self.service_temp = self.get_service(SERVICES_TEMPERATURE_SENSOR)
        self.char_temp = self.service_temp. \
            get_characteristic(CHAR_CURRENT_TEMPERATURE)

    def _set_services(self):
        super()._set_services()
        self.add_service(get_serv_loader().get(SERVICES_TEMPERATURE_SENSOR))

    def set_default_info(self):
        service_info = self.get_service(SERVICES_ACCESSORY_INFO)
        service_info.get_characteristic(CHAR_MODEL) \
            .set_value(self._entity_id)
        service_info.get_characteristic(CHAR_MANUFACTURER) \
            .set_value(HOMEASSISTANT)
        service_info.get_characteristic(CHAR_SERIAL_NUMBER) \
            .set_value('0000')

    def run(self):
        self.set_default_info()

        state = self._hass.states.get(self._entity_id)
        self.update_temperature(new_state=state)

        async_track_state_change(
            self._hass, self._entity_id, self.update_temperature)

    @callback
    def update_temperature(self, entity_id=None, old_state=None,
                           new_state=None):
        temperature = new_state.state
        if temperature != 'unknown':
            self.char_temp.set_value(float(temperature))

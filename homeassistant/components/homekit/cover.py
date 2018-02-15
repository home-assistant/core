import time

from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change

from homeassistant.components.homekit.const import (
    SERVICES_ACCESSORY_INFO, SERVICES_WINDOW_COVERING,
    CHAR_MODEL, CHAR_MANUFACTURER, CHAR_SERIAL_NUMBER,
    CHAR_CURRENT_POSITION, CHAR_TARGET_POSITION, CHAR_POSITION_STATE,
    HOMEASSISTANT)

from pyhap.loader import get_serv_loader
from pyhap.accessory import Accessory, Category


class Window(Accessory):
    category = Category.WINDOW

    def __init__(self, hass, _LOGGER, entity_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._hass = hass
        self._LOGGER = _LOGGER
        self._entity_id = entity_id
        self.current_position = None
        self.homekit_target = None

        self.service_cover = self.get_service(SERVICES_WINDOW_COVERING)
        self.char_current_position = self.service_cover. \
            get_characteristic(CHAR_CURRENT_POSITION)
        self.char_target_position = self.service_cover. \
            get_characteristic(CHAR_TARGET_POSITION)
        self.char_position_state = self.service_cover. \
            get_characteristic(CHAR_POSITION_STATE)

        self.char_target_position.setter_callback = self.move_cover

    def _set_services(self):
        super()._set_services()
        self.add_service(get_serv_loader().get(SERVICES_WINDOW_COVERING))

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
        self.update_cover_position(new_state=state)

        async_track_state_change(
            self._hass, self._entity_id, self.update_cover_position)

        # self.debug_characteristics()

    def debug_characteristics(self):
        while not self.run_sentinel.wait(5):
            self._LOGGER.debug("%s: Target: %d", self._entity_id,
                self.char_target_position.get_value())
            self._LOGGER.debug("%s: Current: %d", self._entity_id,
                self.char_current_position.get_value())
            self._LOGGER.debug("%s: PositionState: %d", self._entity_id,
                self.char_position_state.get_value())

    def move_cover(self, value):
        if value != self.current_position:
            self._LOGGER.debug("%s: Set position to %d", self._entity_id, value)
            self.homekit_target = value
            if value > self.current_position:
                self.char_position_state.set_value(1)
            elif value < self.current_position:
                self.char_position_state.set_value(0)
            self._hass.services.call(
                'cover', 'set_cover_position', 
                {'entity_id': self._entity_id, 'position': value})

    @callback
    def update_cover_position(self, entity_id=None, old_state=None,
                              new_state=None):
        if new_state is None:
            return

        self.current_position = int(new_state.attributes['current_position'])
        self.char_current_position.set_value(self.current_position)

        if self.homekit_target is None or \
            abs(self.current_position - self.homekit_target) < 6:
            self.char_target_position.set_value(self.current_position)
            self.char_position_state.set_value(2)
            self.homekit_target = None

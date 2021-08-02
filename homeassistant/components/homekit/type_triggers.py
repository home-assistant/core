"""Class to hold all sensor accessories."""
import logging

from pyhap.const import CATEGORY_SENSOR

from .accessories import TYPES, HomeAccessory
from .const import CHAR_PROGRAMMABLE_SWITCH_EVENT, SERV_STATELESS_PROGRAMMABLE_SWITCH

_LOGGER = logging.getLogger(__name__)


@TYPES.register("DeviceTriggerAccessory")
class DeviceTriggerAccessory(HomeAccessory):
    """Generate a TemperatureSensor accessory for a temperature sensor.

    Sensor entity must return temperature in °C, °F.
    """

    def __init__(self, *args, device_triggers=None):
        """Initialize a TemperatureSensor accessory object."""
        super().__init__(*args, category=CATEGORY_SENSOR)
        for trigger in device_triggers:
            _LOGGER.warning("Set up up trigger: %s", trigger)
            type = trigger.get("type")
            sub_type = trigger.get("sub_type")
            serv_stateless_switch = self.add_preload_service(
                SERV_STATELESS_PROGRAMMABLE_SWITCH
            )
            self._triggers[(type, sub_type)] = serv_stateless_switch.configure_char(
                CHAR_PROGRAMMABLE_SWITCH_EVENT,
                value=0,
                valid_values={"Press": 0},
            )

    # Attach the trigger using the helper in async run
    # and detach it in async stop

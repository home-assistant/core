"""
Extends rpi_i2c_chips exapander extension for HA
"""

import logging
import threading

from .rpi_i2c_chips import MCP23018, PCF8574

from homeassistant.helpers.entity import ToggleEntity
from homeassistant.components.binary_sensor import BinarySensorDevice

_LOGGER = logging.getLogger(__name__)


class HAExpanderMixIn:
    """
    Exapands rpi_i2c_chips classes with HA specific methods/attributes.
    Keeps connection between pins of given chip and HA entities.
    """

    def __init__(self, perform_outputs_verification=True):
        """
        perform_outputs_verification - if set, every write to port
        will be followed by read allowing to verify port state.
        """
        self.pin_connections = {}
        self.perform_outputs_verification = perform_outputs_verification

    def check_pin(self, pin):
        """
        Check if given pin is valid
        """
        if 0 <= pin < self.PIN_COUNT:
            return
        raise ValueError("Pin %r is invalid for %r", pin, self)

    def pin_connect(self, pin, dev):
        """
        Assings pin to work with HA switch/sensor
        """
        self.check_pin(pin)
        prev_connection = self.pin_connections.get(pin)
        if prev_connection:
            raise ValueError(
                "Unable to connect %r to pin %r. Pin already connected to: %r."
                % (dev, pin, prev_connection)
            )
        self.pin_connections[pin] = dev

    def get_pin_dev(self, pin):
        return self.pin_connections.get(pin)

    def ha_configure(self):
        """
        Performs HW init based on homeassistant connections.
        """
        inputs_mask = 0
        outputs_mask = 0
        outputs_on_mask = 0
        pull_up_mask = 0

        for pin, dev in self.pin_connections.items():
            if isinstance(dev, ToggleEntity):
                outputs_mask += 2 ** pin
                pull_up_mask += 2 ** pin
                if dev.is_pin_high:
                    outputs_on_mask += 2 ** pin
            elif isinstance(dev, BinarySensorDevice):
                inputs_mask += 2 ** pin
                pull_up_mask += 2 ** pin
            else:
                raise RuntimeError(
                    "Unable assign %r to expander input/outputs" % (dev,)
                )
        _LOGGER.debug(
            "Calculated masks: inputs :0x%X  outputs: 0x%X , "
            "outputs_on: 0x%X for %r",
            inputs_mask,
            outputs_mask,
            outputs_on_mask,
            self,
        )
        # TODO: Pass outputs state to configure without HW flipping ?
        self.configure(outputs_mask, inputs_mask, pull_up_mask)

    def update_outputs(self):
        """
        Sets HW outputs depending on state of HA switches.
        Performs HW chip reconfiguration if outputs state mismatch detected.
        """
        outputs_on_mask = 0
        for pin, dev in self.pin_connections.items():
            if isinstance(dev, ToggleEntity):
                if dev.is_pin_high:
                    outputs_on_mask += 2 ** pin
        self.set_outputs(outputs_on_mask)
        if self.perform_outputs_verification:
            if not self.verify_outputs():
                _LOGGER.warn(
                    "Outputs state wrong. "
                    "Performing HW configuration again (%s).",
                    self,
                )
                self.ha_configure()
                self.set_outputs(outputs_on_mask)
                if self.verify_outputs():
                    _LOGGER.warn(
                        "Outputs state corrected. Reconfigured %s .", self
                    )
                else:
                    _LOGGER.error(
                        "Outputs state wrong and unable to reconfigure %s .",
                        self,
                    )


class HA_MCP23018(MCP23018.MCP23018, HAExpanderMixIn):
    id = "MCP23018"

    def __init__(self, bus, address):
        MCP23018.MCP23018.__init__(self, bus, address)
        HAExpanderMixIn.__init__(self)


# NOTE MCP23017 seems be same as MCP23018 in terms of I²C bus operations
class HA_MCP23017(HA_MCP23018):
    id = "MCP23017"


class HA_PCF8574(PCF8574.PCF8574, HAExpanderMixIn):
    """
    """

    id = "PCF8574"

    def __init__(self, bus, address):
        PCF8574.PCF8574.__init__(self, bus, address)
        HAExpanderMixIn.__init__(self)


class SupportedExpanders:
    """
    Keeps mapping from ids to chip HAExpander classes.
    """

    chip_class_per_id = {}

    def __init__(self):
        self.add_chip_class(HA_MCP23017)
        self.add_chip_class(HA_MCP23018)
        self.add_chip_class(HA_PCF8574)

    def add_chip_class(self, haexpander_class):
        self.chip_class_per_id[haexpander_class.id] = haexpander_class

    def get_chip_class(self, haexpander_class_id):
        return self.chip_class_per_id.get(haexpander_class_id)

    def chip_ids(self):
        return sorted(self.chip_class_per_id.keys())


class ManagedChips:
    """
    Keeps track of managed chips on given bus.
    Configures managed chips to act as sensors/switches.
    """

    def __init__(self, bus):
        # Static list of supported exapnders:
        self.supported_expanders = SupportedExpanders()
        # Chips marked to manage:
        self.chip_per_address = {}
        # Request for adding chips on buses may come from differnet components
        # (switches/sensors) and different threads, so lock needed
        self.lock = threading.Lock()
        # Bus to operate on.
        self.bus = bus

    def manage_chip(self, address, chip_id):
        with self.lock:
            chip = self.chip_per_address.get(address)
            if chip:
                if chip.id != chip_id:
                    raise ValueError(
                        "Chip (%r) with different id (%r)"
                        " than expected already managed on address %x"
                        % (chip, chip.id, chip_id, address)
                    )
            else:
                chip_class = self.supported_expanders.get_chip_class(chip_id)
                if chip_class is None:
                    raise ValueError("Unknown chip id: %r" % (chip_id,))
                chip = chip_class(self.bus, address)
                self.chip_per_address[address] = chip
                _LOGGER.info(
                    "New chip (%r) managed on bus: %r address: %x in %r",
                    chip,
                    self.bus,
                    address,
                    self,
                )
            return chip

    def chips(self):
        for chip in self.chip_per_address.values():
            yield chip

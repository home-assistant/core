"""Support for I2C MCP23017 chip."""
import logging
import threading

# MCP23017 Register Map
IODIRA = 0x00
IODIRB = 0x01
IPOLA = 0x02
IPOLB = 0x03
GPINTENA = 0x04
GPINTENB = 0x05
DEFVALA = 0x06
DEFVALB = 0x07
INTCONA = 0x08
INTCONB = 0x09
IOCONA = 0x0A
IOCONB = 0x0B
GPPUA = 0x0C
GPPUB = 0x0D
INTFA = 0x0E
INTFB = 0x0F
INTCAPA = 0x10
INTCAPB = 0x11
GPIOA = 0x12
GPIOB = 0x13
OLATA = 0x14
OLATB = 0x15

_LOGGER = logging.getLogger(__name__)


class MCP23017:
    """MCP23017 device driver."""

    def __init__(self, bus, address):
        """Create a MCP23017 instance at {address} on I2C {bus}."""
        self._bus = bus
        self._address = address

        self._device_lock = threading.Lock()
        self._cache = {
            "IODIR": (self[IODIRB] << 8) + self[IODIRA],
            "GPPU": (self[GPPUB] << 8) + self[GPPUA],
            "GPIO": (self[GPIOB] << 8) + self[GPIOA],
            "OLAT": (self[OLATB] << 8) + self[OLATA],
        }
        self._input_callbacks = [None for i in range(16)]
        self._update_bitmap = 0

        _LOGGER.info("%s @ 0x%02x device created", type(self).__name__, address)

    def __enter__(self):
        """Lock access to device (with statement)."""
        self._device_lock.acquire()
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        """Unlock access to device (with statement)."""
        self._device_lock.release()
        return False

    def __setitem__(self, register, value):
        """Set MCP23017 {register} to {value}."""
        self._bus.write_byte_data(self._address, register, value)

    def __getitem__(self, register):
        """Get value of MCP23017 {register}."""
        data = self._bus.read_byte_data(self._address, register)
        return data

    def _get_register_value(self, register, bit):
        """Get MCP23017 {bit} of {register}."""
        if bit < 8:
            value = self[globals()[register + "A"]] & 0xFF
            self._cache[register] = self._cache[register] & 0xFF00 | value
        else:
            value = self[globals()[register + "B"]] & 0xFF
            self._cache[register] = self._cache[register] & 0x00FF | (value << 8)

        return bool(value & (1 << bit))

    def _set_register_value(self, register, bit, value):
        """Set MCP23017 {bit} of {register} to {value}."""
        # Update cache
        cache_old = self._cache[register]
        if value:
            self._cache[register] |= (1 << bit) & 0xFFFF
        else:
            self._cache[register] &= ~(1 << bit) & 0xFFFF
        # Update device register only if required (minimize # of I2C  transactions)
        if cache_old != self._cache[register]:
            if bit < 8:
                self[globals()[register + "A"]] = self._cache[register] & 0xFF
            else:
                self[globals()[register + "B"]] = (self._cache[register] >> 8) & 0xFF

    @property
    def address(self):
        """Return device address."""
        return self._address

    # -- Called from HA thread pool

    def get_pin_value(self, pin):
        """Get MCP23017 GPIO[{pin}] value."""
        with self:
            return self._get_register_value("GPIO", pin)

    def set_pin_value(self, pin, value):
        """Set MCP23017 GPIO[{pin}] to {value}."""
        with self:
            self._set_register_value("OLAT", pin, value)

    def set_input(self, pin, is_input):
        """Set MCP23017 GPIO[{pin}] as input."""
        with self:
            self._set_register_value("IODIR", pin, is_input)

    def set_pullup(self, pin, is_pullup):
        """Set MCP23017 GPIO[{pin}] as pullup."""
        with self:
            self._set_register_value("GPPU", pin, is_pullup)

    def register_input_callback(self, pin, callback):
        """Register callback for state change."""
        with self:
            self._input_callbacks[pin] = callback
            # Trigger a callback to update initial state
            self._update_bitmap |= (1 << pin) & 0xFFFF

    # -- Called from bus manager thread

    def run(self):
        """Poll all ports once and call corresponding callback if a change is detected."""
        with self:
            # Read pin values for bank A and B from device if there are associated callbacks (minimize # of I2C  transactions)
            input_state = self._cache["GPIO"]
            if any(self._input_callbacks[0:8]):
                input_state = input_state & 0xFF00 | self[GPIOA]
            if any(self._input_callbacks[8:16]):
                input_state = input_state & 0x00FF | (self[GPIOB] << 8)

            # Check pin values that changed and update input cache
            self._update_bitmap = self._update_bitmap | (
                input_state ^ self._cache["GPIO"]
            )
            self._cache["GPIO"] = input_state

            # Call callback functions only for pin that changed
            for pin in range(16):
                if (self._update_bitmap & 0x1) and self._input_callbacks[pin]:
                    self._input_callbacks[pin](bool(input_state & 0x1))
                    self._update_bitmap &= ~(1 << pin) & 0xFFFF
                input_state >>= 1
                self._update_bitmap >>= 1

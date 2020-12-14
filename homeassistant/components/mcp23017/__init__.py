"""Support for I2C MCP23017 chip."""

import functools
import logging
import threading

from homeassistant.components.i2c.const import DOMAIN as DOMAIN_I2C
from homeassistant.helpers import device_registry

from .const import (
    CONF_FLOW_PIN_NUMBER,
    CONF_FLOW_PLATFORM,
    CONF_I2C_ADDRESS,
    DEFAULT_PUSH_SLOWDOWN,
    DOMAIN,
)

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

PLATFORMS = ["binary_sensor", "switch"]


async def async_setup(hass, config):
    """Set up the component."""

    # hass.data[DOMAIN] store one entry for each MCP23017 instance using i2c address as a key
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass, config_entry):
    """Set up the MCP23017 from a config entry."""

    i2c_address = config_entry.data[CONF_I2C_ADDRESS]
    if i2c_address not in hass.data[DOMAIN]:
        try:
            bus = hass.data[DOMAIN_I2C]
            hass.data[DOMAIN][i2c_address] = MCP23017(bus, i2c_address)

        except (OSError, ValueError, KeyError) as error:
            await hass.config_entries.async_remove(config_entry.entry_id)
            hass.components.persistent_notification.create(
                f"Error: {error}<br /> Unable to create MCP23017 device at address 0x{i2c_address:02x}",
                title=f"{DOMAIN} Configuration",
                notification_id=f"{DOMAIN} notification",
            )

            _LOGGER.error(
                "Unable to create MCP23017 device at address 0x%02x",
                i2c_address,
            )

            return False

        # Register a device combining all related platforms
        devices = await device_registry.async_get_registry(hass)
        devices.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, i2c_address)},
            manufacturer="MicroChip",
            model=DOMAIN,
            name=f"{DOMAIN} @0x{i2c_address:02x}",
        )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(
            config_entry, config_entry.data[CONF_FLOW_PLATFORM]
        )
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload MCP23017 platform corresponding to a config_entry."""

    await hass.config_entries.async_forward_entry_unload(
        config_entry, config_entry.data[CONF_FLOW_PLATFORM]
    )

    # Remove related platform from component
    i2c_address = config_entry.data[CONF_I2C_ADDRESS]
    device = hass.data[DOMAIN][i2c_address]

    await hass.async_add_executor_job(
        functools.partial(
            device.unregister_entity, config_entry.data[CONF_FLOW_PIN_NUMBER]
        )
    )

    if device.has_no_entities:
        await hass.async_add_executor_job(device.destroy)
        del hass.data[DOMAIN][i2c_address]

        _LOGGER.info("%s@0x%02x device destroyed", type(device).__name__, i2c_address)

    return True


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
        self._entities = [None for i in range(16)]
        self._push_slowdown = DEFAULT_PUSH_SLOWDOWN
        self._push_slowdown_counter = 0
        self._update_bitmap = 0

        self._bus.register_device(self)

        _LOGGER.info("%s@0x%02x device created", type(self).__name__, address)

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

    @property
    def unique_id(self):
        """Return component unique id."""
        return f"{DOMAIN}-{self.address}"

    @property
    def has_no_entities(self):
        """Check if there are no more entities attached."""
        return not any(self._entities)

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

    def register_entity(self, entity):
        """Register entity to this device instance."""
        with self:
            self._entities[entity.pin] = entity

            # Trigger a callback to update initial state
            self._update_bitmap |= (1 << entity.pin) & 0xFFFF

            _LOGGER.info(
                "%s(pin %d:'%s') attached to %s@0x%02x",
                type(entity).__name__,
                entity._pin_number,
                entity._pin_name,
                type(self).__name__,
                self.address,
            )

        return True

    def unregister_entity(self, pin_number):
        """Unregister entity from the device."""
        with self:
            entity = self._entities[pin_number]
            entity.unsubscribe_update_listener()
            self._entities[pin_number] = None

            _LOGGER.info(
                "%s(pin %d:'%s') removed from MCP23017@0x%02x",
                type(entity).__name__,
                entity.pin,
                entity.name,
                self._address,
            )

    def destroy(self):
        """Handle steps required before object destruction."""
        # Free up i2c bus at component's address
        self._bus.unregister_device(self)

    # -- Called from bus manager thread

    def run(self):
        """Poll all ports once and call corresponding callback if a change is detected."""
        with self:
            self._push_slowdown_counter -= 1
            if self._push_slowdown_counter <= 0:
                self._push_slowdown_counter = self._push_slowdown

                # Read pin values for bank A and B from device if there are associated callbacks (minimize # of I2C  transactions)
                input_state = self._cache["GPIO"]
                if any(
                    [hasattr(entity, "push_update") for entity in self._entities[0:8]]
                ):
                    input_state = input_state & 0xFF00 | self[GPIOA]
                if any(
                    [hasattr(entity, "push_update") for entity in self._entities[8:16]]
                ):
                    input_state = input_state & 0x00FF | (self[GPIOB] << 8)

                # Check pin values that changed and update input cache
                self._update_bitmap = self._update_bitmap | (
                    input_state ^ self._cache["GPIO"]
                )
                self._cache["GPIO"] = input_state
                # Call callback functions only for pin that changed
                for pin in range(16):
                    if (self._update_bitmap & 0x1) and hasattr(
                        self._entities[pin], "push_update"
                    ):
                        self._entities[pin].push_update(bool(input_state & 0x1))
                        self._update_bitmap &= ~(1 << pin) & 0xFFFF
                    input_state >>= 1
                    self._update_bitmap >>= 1

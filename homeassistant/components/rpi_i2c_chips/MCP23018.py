import logging
import time

from .register import Register
from .common import Expander

module_logger = logging.getLogger(__name__)
module_logger.setLevel(logging.DEBUG)


class MCP23018(Expander):
    """
    MCP23018 register definitions
    """

    # Common to all Exapnders
    PIN_COUNT = 16
    MASK = (1 << PIN_COUNT) - 1  # 0xffff

    # We use default PoR BANK=0 ports adresses
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
    IOCON = 0x0A
    # IOCON    = 0x0b  # duplicate
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

    # BANK=1 adresses
    #    IODIRA   = 0x00
    #    IPOLA    = 0x01
    #    GPINTENA = 0x02
    #    DEFVALA  = 0x03
    #    INTCONA  = 0x04
    #    IOCON    = 0x05
    #    GPPUA    = 0x06
    #    INTFA    = 0x07
    #    INTCAPA  = 0x08
    #    GPIOA    = 0x09
    #    OLATA    = 0x0a
    #
    #    IODIRB   = 0x10
    #    IPOLB    = 0x11
    #    GPINTENB = 0x12
    #    DEFVALB  = 0x13
    #    INTCONB  = 0x14
    #    # IOCON    = 0x05   # duplicate
    #    GPPUB    = 0x16
    #    INTFB    = 0x17
    #    INTCAPB  = 0x18
    #    GPIOB    = 0x19
    #    OLATB    = 0x1a

    def __init__(self, bus, address, log=module_logger):
        if address < 0x20 or address >= 0x20 + 8:
            raise ValueError(
                "Invalid device address: 0x%x for MCP23018" % (address,)
            )
        super().__init__(bus, address, log)

    def reset(self):
        """Sets chip like after power on reset.
        """
        # TODO: What if chip is in BANK=1 mode ?
        self.set_inputs(0xFFFF)

    class IOCON_Register(Register):
        """ IOCON – I/O EXPANDER CONFIGURATION REGISTER

        MIRROR = 1, the INTn pins are functionally
            OR’ed so that an interrupt on either port will cause
            both pins to activate
        MIRROR = 0, the INT pins are separated.
            Interrupt conditions on a port will cause its respecive
            INT pin to activate

        """

        _bitnames = Register.parse_bitnames(
            "BANK MIRROR SEQOP _ _ ODR INTPOL INTCC"
        )
        _bitaliases = Register.parse_bitaliases(_bitnames)

    def set_IOCON(self, reg):  # TODO : rename to set_IOCON ?
        """
        """
        if conf_reg.BANK != 0:
            raise ValueError("Switching to BANK=1 mode not implemented")
        self.bus_write_byte_data(self.IOCON, int(reg))

    def read_IOCON(self):
        val = self.bus_read_byte_data(self.IOCON)
        return self.IOCON_Register(val)

    class IODIR_Register(Register):
        """  IODIR – I/O DIRECTION REGISTER
        When a bit is set, the corresponding pin becomes an input.
        When a bit is clear, the corresponding pin becomes an output.
        """

        _bitnames = Register.gen_bitnames(8, "IO")  # IO7 .. IO0
        _bitaliases = Register.parse_bitaliases(_bitnames)

    def set_IODIRA(self, iodir_register):
        self.bus_write_byte_data(self.IODIRA, int(iodir_register))

    def set_IODIRB(self, iodir_register):
        self.bus_write_byte_data(self.IODIRB, int(iodir_register))

    def read_IODIRA(self):
        val = self.bus_read_byte_data(self.IODIRA)
        return self.IODIR_Register(val)

    def read_IODIRB(self):
        val = self.bus_read_byte_data(self.IODIRB)
        return self.IODIR_Register(val)

    class IPOL_Register(Register):
        """   IPOL – INPUT POLARITY PORT REGISTER
        If a bit is set, the corresponding GPIO register bit will
        reflect the inverted value on the pin.
        """

        _bitnames = Register.gen_bitnames(8, "IP")  # IP7 .. IP0
        _bitaliases = Register.parse_bitaliases(_bitnames)

    def set_IPOLA(self, ipol_register):
        self.bus_write_byte_data(self.IPOLA, int(ipol_register))

    def set_IPOLB(self, ipol_register):
        self.bus_write_byte_data(self.IPOLB, int(ipol_register))

    def read_IPOLA(self):
        val = self.bus_read_byte_data(self.IPOLA)
        return self.IPOL_Register(val)

    def read_IPOLB(self):
        val = self.bus_read_byte_data(self.IPOLB)
        return self.IPOL_Register(val)

    class GPPU_Register(Register):
        """The GPPU register controls the pull-up resistors for the
        port pins. If a bit is set the corresponding port pin is
        internally pulled up with an internal resistor.
        150 microA for 3.3V in 25°C
        """

        _bitnames = Register.gen_bitnames(8, "PU")  # PU7 .. PU0
        _bitaliases = Register.parse_bitaliases(_bitnames)

    def set_GPPUA(self, gppu_register):
        self.bus_write_byte_data(self.GPPUA, int(gppu_register))

    def set_GPPUB(self, gppu_register):
        self.bus_write_byte_data(self.GPPUB, int(gppu_register))

    def read_GPPUA(self):
        val = self.bus_read_byte_data(self.GPPUA)
        return self.GPPU_Register(val)

    def read_GPPUB(self):
        val = self.bus_read_byte_data(self.GPPUB)
        return self.GPPU_Register(val)

    def set_GPPU(self, mask):
        self.bus_write_byte_data(self.GPPUA, mask & 0xFF)
        self.bus_write_byte_data(self.GPPUB, (mask >> 8) & 0xFF)

    def read_GPPU(self, mask):
        mask = self.bus_read_byte_data(self.GPPUA)
        mask |= self.bus_read_byte_data(self.GPPUB) << 8
        return mask

    class GPIO_Register(Register):
        """ The GPIO register reflects the value on the port.
        Reading from this register reads the port. Writing to this
        register modifies the Output Latch (OLAT) register.
        """

        # gen_bitnames(num, prefix)
        _bitnames = Register.gen_bitnames(8, "GP")  # GP7 .. GP0
        _bitaliases = Register.parse_bitaliases(_bitnames)

    def set_GPIOA(self, gpio_register):
        self.bus_write_byte_data(self.GPIOA, int(gpio_register))

    def set_GPIOB(self, gpio_register):
        self.bus_write_byte_data(self.GPIOB, int(gpio_register))

    def read_GPIOA(self):
        val = self.bus_read_byte_data(self.GPIOA)
        return self.GPIO_Register(val)

    def read_GPIOB(self):
        val = self.bus_read_byte_data(self.GPIOB)
        return self.GPIO_Register(val)

    def set_GPIO(self, mask):
        self.bus_write_byte_data(self.GPIOA, mask & 0xFF)
        self.bus_write_byte_data(self.GPIOB, (mask >> 8) & 0xFF)

    def read_GPIO(self):
        mask = self.bus_read_byte_data(self.GPIOA)
        mask |= self.bus_read_byte_data(self.GPIOB) << 8
        # TODO: Should use 16bit wide GPIO_Register16
        # having GPA0..GPA7,GPB0..GPB7 ?
        return mask

    def configure(self, outputs_mask, inputs_mask, pull_ups_mask):
        """
        Configures chip:
        outputs_mask - whose pins became outputs, rest is configure inputs
        inputs_mask - whose pins became inputs, must not overlap with inputs
        pull_ups_mask - whose pins have pull ups set,

        Only inputs/outputs_mask is configure, rest is left untouched.
        pull_up_mask can be only set for inputs/outputs

        Configuraiton tries to preserve previous state of
        chip as much as possible.

        """
        self.log.debug(
            "CALLED: configure(%s,outputs_mask=%r,"
            "inputs_mask=%r,pull_up_mask=%r) ",
            self,
            outputs_mask,
            inputs_mask,
            pull_ups_mask,
        )

        super().configure(outputs_mask, inputs_mask, pull_ups_mask)

        outputs_mask_b, outputs_mask_a = self.mask_split2bytes(
            self.outputs_mask
        )
        # When a bit is zero, the corresponding pin becomes an output.
        self.set_IODIRA(self.byte_invert(outputs_mask_a))
        self.set_IODIRB(self.byte_invert(outputs_mask_b))

        pull_ups_mask_b, pull_ups_mask_a = self.mask_split2bytes(
            self.pull_ups_mask
        )
        self.set_GPPUA(pull_ups_mask_a)
        self.set_GPPUB(pull_ups_mask_b)

    def set_outputs(self, mask):
        mask = self.mask(mask)
        self.set_outputs_a(mask & 0xFF)
        self.set_outputs_b((mask >> 8) & 0xFF)
        self.outputs_state = mask
        self.log.debug("%s set_outputs(mask=0x%X).", self, self.outputs_state)

    def verify_outputs(self):
        """
        Checks if actual outputs state is same as supposed
        """
        gpio = self.read_GPIO()
        actual_outputs_mask = int(gpio) & self.outputs_mask
        # Inputs state: 65535 (0xFFFF) usually means chip was reset.
        self.log.debug(
            "Verified inputs state: %s (0x%X) "
            "outputs_masked: 0x%X expected: 0x%X",
            gpio,
            int(gpio),
            actual_outputs_mask,
            self.outputs_state,
        )
        if actual_outputs_mask != self.outputs_state:
            # NOTE: Below we work on real ports state, not logical,
            # as values may be inverted.
            self.log.warn(
                "Outputs state mismatch. Read inputs: 0x%X, "
                "outputs_masked: 0x%X but expected: 0x%X",
                int(gpio),
                actual_outputs_mask,
                self.outputs_state,
            )
            return False
        return True

    def set_outputs_a(self, mask):
        self.bus_write_byte_data(self.OLATA, mask)

    def set_outputs_b(self, mask):
        self.bus_write_byte_data(self.OLATB, mask)

    def read_inputs(self):
        # NOTE: We can't get information about outputs
        # by reading inputs in MCP23018
        input_vals = int(self.read_GPIO())
        # self.log.debug("read_inputs(): read GPIO: 0x%X inputs mask: 0x%X "
        # "expected outputs state: 0x%X",
        # input_vals, self.inputs_mask, self.outputs_state, )
        input_vals &= self.inputs_mask
        return input_vals


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(relativeCreated)6d %(threadName)s %(message)s",
    )

    import smbus

    # bus = smbus.SMBus(0)  # Rev 1 Pi uses 0
    bus1 = smbus.SMBus(1)  # Rev 2 Pi uses 1
    mcp23018 = MCP23018(bus1, 0x20)

    if 1:  # Configuration write test
        conf_reg = mcp23018.read_configuration()
        # Fails on first run with OSError:
        #   [Errno 121] Remote I/O error on return
        #   self.bus.read_byte_data(self.address, cmd) ???
        # https://stackoverflow.com/questions/15245235/input-output-error-using-python-module-smbus-a-raspberry-pi-and-an-arduino
        # subprocess.call(['i2cdetect', '-y', '1'])
        # i2cdetect -y 1

        print("Initial conf_reg: %s" % (conf_reg,))
        conf_reg.MIRROR = 1
        mcp23018.set_configuration(conf_reg)
        conf_reg = mcp23018.read_configuration()
        print("After updated conf_reg: %s (MIRROR should be 1)" % (conf_reg,))
        conf_reg.MIRROR = 0
        mcp23018.set_configuration(conf_reg)
        conf_reg = mcp23018.read_configuration()
        print(
            "After 2nd updated conf_reg: %s (MIRROR should be 0)" % (conf_reg,)
        )

    if 1:
        outputs_mask = 0x0001
        print("Blinking 1Hz on 0x%04x outputs" % (outputs_mask,))
        # configure(self, output_mask, invert_mask, pull_up_mask):
        # Setting all IO ports as outputs

        mcp23018.configure(
            outputs_mask, mcp23018.MASK - outputs_mask, 0, 0xFFFF
        )

        for i in range(10):
            mcp23018.set_outputs(0)  # All low, draining
            time.sleep(0.5)
            mcp23018.set_outputs(0xFFFF)  # All high, no current
            time.sleep(0.5)
        print("Blinking done.")

    if 0:
        print("Reading all inputs in endless loop.. Hit CTRL+C to stop.")
        # Set Pullups on all outputs, so they will stay high,
        # but shorting to GND (via pressing button) will drive them low
        # mcp23018.configure_inputs(0xffff, set_pull_ups = True, invert=True)

        # Same as above, but only on GPA7 & GPA6
        input_reg = mcp23018.GPIO_Register()
        input_reg.GP7 = 1
        input_reg.GP6 = 1
        mcp23018.configure_inputs(input_reg, set_pull_ups=True, invert=True)

        while 1:
            gpio = mcp23018.read_GPIO()
            gpio_a = mcp23018.read_GPIOA()
            print("gpio: %04x -> A: %s" % (int(gpio), str(gpio_a)))
            time.sleep(0.1)

    if 0:
        print(
            "Detecting pushbutton hits via interrputs in endless loop... "
            "Hit CTRL+C to stop."
        )
        mcp23018.set_io_direction_input(0xFFFF)  # 0 means output
        # Set Pullups on all outputs, so they will stay high,
        # but short to GND will drive them low
        mcp23018.set_GPPU(0xFFFF)
        # Enable interrputs
        mcp23018.set_interrupt_on_change(0x0000)  # Turn off interrupts
        # Configure interrputs to trigger on value different than in DEFVAL
        mcp23018.set_INTCON(0x1111)
        gpio = mcp23018.read_gpio()
        # Set default values for interrupt as read from gpio
        mcp23018.set_DEFVAL(gpio)
        mcp23018.set_interrupt_on_change(0xFFFF)  # Turn on interrupts

        last_gpio = None
        last_intf = None
        last_intcap = None
        while 1:
            intcap = mcp23018.read_INTCAP()
            # gpio = mcp23018.read_gpio()  # NOTE: Reading GPIO clears INTCAP
            intf = mcp23018.read_INTF()

            if gpio != last_gpio or intf != last_intf or intcap != last_intcap:
                print(
                    "gpio: %04x intf: %04x intcap: %04x" % (gpio, intf, intcap)
                )
            last_gpio = gpio
            last_intf = intf
            last_intcap = intcap
            time.sleep(0.2)

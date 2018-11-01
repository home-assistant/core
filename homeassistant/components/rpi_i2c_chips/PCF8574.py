import logging

from .register import Register
from .common import Expander

module_logger = logging.getLogger(__name__)
# module_logger.setLevel(logging.DEBUG)


class PCF8574(Expander):
    """
    PCF8574 register/operation definitions
    """

    # Common to all Exapnders
    PIN_COUNT = 8
    MASK = (1 << PIN_COUNT) - 1  # 0xff

    def __init__(self, bus, address, log=module_logger):
        if (
            address < 0x20 or address >= 0x20 + 8
        ):  # TODO: Move to verify_bus_address() ?
            raise ValueError(
                "Invalid device address: 0x%x for PCF8574" % (address,)
            )
        super().__init__(bus, address, log=log)
        self.log.debug("%s @ 0x%x init done", self, self.address)

    class Port_Register(Register):
        """ 
        Only PCF8574 register representing both I/O ports
        """

        _bitnames = Register.gen_bitnames(8, "P")  # P7 .. P0

    def reset(self):
        """Sets chip like after power on reset.
        """
        # from official docs:  At power-on the I/Os are HIGH.
        self.write_byte(0xFF)

    def configure(self, outputs_mask, inputs_mask, pull_ups_mask=None):
        """
        Configures chip:
        outputs_mask - whose pins became outputs, rest is configure inputs
        inputs_mask - whose pins became inputs, must not overlap with inputs
        pull_ups_mask - whose pins have pull ups set, 

        Only inputs/outputs_mask is configure, rest is left untouched.
        pull_ups_mask can be only set for inputs/outputs

        Configuraiton tries to preserve previous state of chip as much as possible.

        """
        self.log.debug(
            "CALLED: configure(%s,outputs_mask=0x%X,inputs_mask=0x%X,pull_ups_mask=0x%X) ",
            self,
            outputs_mask,
            inputs_mask,
            pull_ups_mask,
        )

        # All inputs must be pulled up to work in PCF8674.
        if pull_ups_mask is None:
            pull_ups_mask = inputs_mask
        super().configure(outputs_mask, inputs_mask, pull_ups_mask)
        io_mask = outputs_mask | inputs_mask
        if pull_ups_mask & self.mask_invert(io_mask):
            raise ValueError(
                "Pull-ups mask (0x%x) set out of inputs (0x%s) and outputs (%x)"
                % (pull_ups_mask,)
            )
        old_state = int(self.read_byte())  # Reading previous state
        new_state = old_state | inputs_mask  # setting inputs to high (pullup)
        if (inputs_mask & pull_ups_mask) != inputs_mask:
            raise ValueError(
                "In PCF8674 all inputs are pulled up by definition"
            )
        self.write_byte(new_state)
        self.log.debug(
            "%s configure()d. state: %s (io pins: 0x%X).",
            self,
            self.state_info(),
            new_state,
        )

    def set_outputs(self, mask):
        """
        Sets expander outputs to given state.
        """
        self.outputs_state = mask
        # We have to keep inputs high to be able detect changes.
        mask |= self.inputs_mask
        self.write_byte(int(mask))
        self.log.debug("%s set_outputs(mask=0x%x).", self, mask)

    def verify_outputs(self):
        """
        Returns false if outputs state can be verified and is not correct.
        """
        portval = self.read_byte()
        outputs = portval & self.outputs_mask
        self.log.debug(
            "verify_outputs(): read byte: 0x%X outputs: 0x%X   exptected outputs state: 0x%X",
            portval,
            outputs,
            self.outputs_state,
        )
        if outputs != self.outputs_state:
            self.log.warn(
                "verify_outputs(): read byte: 0x%X outputs: 0x%X  exptected outputs state: 0x%X mismatch.",
                portval,
                outputs,
                self.outputs_state,
            )
            return False
        return True

    def read_inputs(self):
        inputs = self.read_byte()
        if 1:  # Double check
            if self.outputs_mask != None and self.outputs_state != None:
                outputs = inputs & self.outputs_mask
                ## self.log.debug("read_inputs(): read byte: 0x%X outputs: 0x%X  exptected outputs state: 0x%X", inputs, outputs, self.outputs_state, )
                if outputs != self.outputs_state:
                    self.log.warn(
                        "read_inputs(): read byte: 0x%X outputs: 0x%X mismatch: expected outputs: 0x%X .",
                        inputs,
                        outputs,
                        self.outputs_state,
                    )
        inputs &= self.inputs_mask
        return inputs


if __name__ == "__main__":
    # Run as:
    #   python3 -m rpi_i2c_chips.PCF8574

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(relativeCreated)6d %(threadName)s %(message)s",
    )

    import smbus

    # bus = smbus.SMBus(0)  # Rev 1 Pi uses 0
    bus1 = smbus.SMBus(1)  # Rev 2 Pi uses 1
    pcf8574 = PCF8574(bus1, 0x24)
    pcf8574.set_outputs(0xFF)
    val = pcf8574.read_inputs()
    print("Got %s from %s" % (val, pcf8574))

    pcf8574.set_outputs(0x00)
    val = pcf8574.read_inputs()
    print("Got %s from %s" % (val, pcf8574))

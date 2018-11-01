import logging

module_logger = logging.getLogger(__name__)
module_logger.setLevel(logging.DEBUG)


class Expander:
    PIN_COUNT = None  # Number of outputs and inputs.
    # MASK = (1 << PIN_COUNT) -1  # 0xffff
    MASK = None

    def __init__(self, bus, address, log=module_logger):
        self.bus = bus
        self.address = address
        self.log = log

        # Configuration state of chips
        self.inputs_mask = None   # bits set for input pins.
        self.outputs_mask = None  # bits set for output pins.
        # Last time set and expected state of outputs.
        self.outputs_state = None
        self.pull_ups_mask = None
        # self.invert_mask =  None  # TBA

    def __str__(self):
        return "<%s %s/@0x%02x >" % (self.__class__.__name__, self.bus, self.address, )

    def state_info(self):
        """
        One line info about state
        """
        txt = []
        if self.inputs_mask is None:
            txt.append("inputs: None")
        else:
            txt.append("inputs: 0x%x" % (self.inputs_mask))
        if self.outputs_mask is None:
            txt.append("outputs: None")
        else:
            txt.append("outputs: 0x%x" % (self.outputs_mask))
        if self.outputs_state is None:
            txt.append("outputs_state: None")
        else:
            txt.append("outputs_state: 0x%x" % (self.outputs_state))
        return " ".join(txt)

    #
    # Common classes for all chips
    #

    def mask(self, val):
        """
        Masks given value to chips mask
        """
        return self.MASK & int(val)

    def assert_valid_mask(self, mask):
        if mask < 0 or self.MASK < mask:
            raise ValueError("Invalid mask: %r" % (mask, ))

    def mask_split2bytes(self, mask):
        """
        Splits mask value to 2 bytes.
        """
        mask_a = int(mask) & 0xff
        mask_b = (int(mask) >> 8) & 0xff
        return mask_b, mask_a

    def mask_invert(self, mask):
        """
        Inverts (negates) given mask, keeping result in 0..self.MASK range
        """
        return self.MASK - (mask & self.MASK)

    def byte_invert(self, b):
        return 0xff - (b & 0xff)

    #
    # Bus operations.
    # May allow mixing in other bus type, or adding debug.
    #

    def read_byte(self):
        val = self.bus.read_byte(self.address)
        return val

    def write_byte(self, byte_val):
        val = self.bus.write_byte(self.address, byte_val)
        return val

    def bus_write_byte_data(self, cmd, val):
        self.bus.write_byte_data(self.address, cmd, val)

    def bus_read_byte_data(self, cmd):
        return self.bus.read_byte_data(self.address, cmd)

    #
    # Common expander interface.
    # Needs be implemented in sublcass.
    #

    def reset(self):
        """
        Returns chips to state as it was in power up
        """
        raise NotImplementedError(
            "Must be implemented for specific chip in sub-class")

    def configure(self, outputs_mask, inputs_mask, pull_ups_mask):
        """
        Configures chip:
        outputs_mask - whose pins became outputs, rest is configure inputs
        inputs_mask - currently ignored, negation of outputs_mask is used.
        pull_ups_mask - whose pins have pull ups set

        TBD:
        invert_mask - whose pins are inverted (both inputs/outputs) 

        NOTE: Expand this method in sublcases implementing real HW configuration
        """
        ## raise NotImplementedError("Must be implemented for specific chip in sub-class")
        self.assert_valid_mask(outputs_mask)
        self.assert_valid_mask(inputs_mask)
        # self.assert_valid_mask(invert_mask)
        self.assert_valid_mask(pull_ups_mask)
        if outputs_mask & inputs_mask:
            raise ValueError("Input(0x%x) and output (0x%x) masks overlap." % (
                inputs_mask, outputs_mask, ))

        self.outputs_mask = outputs_mask
        self.inputs_mask = inputs_mask
        ## self.invert_mask =  invert_mask
        self.pull_ups_mask = pull_ups_mask

    def configure_inputs(self, inputs_mask, pull_ups_mask=None):
        """
        Configure subset of pins as inputs. 
        Pins must not be already configured as outputs
        """
        if pull_ups_mask is None:
            # By default use pull_up_mask
            pull_ups_mask = inputs_mask
        else:
            if pull_ups_mask & self.mask_invert(inputs_mask):
                raise ValueError("Pull ups mask (0x%x) outside inputs mask (0x%x)" % (
                    pull_ups_mask, inputs_mask))

        if self.outputs_mask and (self.outputs_mask & inputs_mask):
            raise ValueError("Alredy set outputs: 0x%x overlap with inputs: 0x%x" % (
                self.outputs_mask,  inputs_mask))
        if pull_ups_mask:
            # Preserve already set pull_ups outside inputs mask.
            new_pull_ups_mask = self.pull_ups_mask & self.mask_invert(
                inputs_mask)  # Zeroing coresponding to inputs mask values.
            new_pull_ups_mask |= pull_ups_mask

        self.configure(self.outputs_mask, inputs_mask,  new_pull_ups_mask)

    def set_outputs(self, mask,):
        """
        Sets outputs to given state
        Always set self.outputs_state 
        """
        raise NotImplementedError(
            "Must be implemented for specific chip in sub-class")

    def verify_outputs(self):
        """
        Returns false if outputs state can be verified and is not correct
        """
        return True

    def read_inputs(self):
        """
        Reads state of inputs (and outputs ?)
        Returns Register instance representing inputs state
        TODO: Are output states ale included ?
        """
        raise NotImplementedError(
            "Must be implemented for specific chip in sub-class")

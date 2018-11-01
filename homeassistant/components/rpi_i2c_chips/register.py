#
# class RegisterTypeFactory:
#
#
#
# class Register:
#    _bitnames = ()  # From lowest to highest, None means not used
#    _bitaliases = {}  # Contain extra names, must contain all _bitnames
#
#
#
# def gen_register(name, bitnames):
#    Test = type(name, (object,), {'__init__': __init__, 'printX': printX})
#    @staticlass
#


class Register:
    """
    Represents registers.
    Allows access to bits via names.
    Keep as close as possible to names used in official docs.
    """
    _NOT_USED_BITNAME_ID = "_"
    _bitnames = ()  # Resulf of  parse_bitnames() / gen_bitnames call.
    _bitaliases = {}  # Result of  parse_bitaliases(_bitnames) .
    _mask = None  # base on number of _bitnames .
    _val = None

    @staticmethod
    def parse_bitnames(bitnames_string):
        """Parses bit names given by string seprated by spaces."""
        bitnames = []
        for bitname in bitnames_string.split():
            bitnames.append(bitname.upper())
        return bitnames

    @staticmethod
    def gen_bitnames(num, prefix):
        """Generates num bitnames with given prefix."""
        bitnames = []
        for n in range(num-1, -1, -1):
            bitnames.append("%s%d" % (prefix, n))
        return tuple(bitnames)

    @staticmethod
    def parse_bitaliases(bitnames):
        """
        Generates names mappings to bitmasks.
        """
        bitaliases = {}
        bitmask = 1 << (len(bitnames)-1)

        for bitname in bitnames:
            bitaliases[bitname] = bitmask
            bitmask = bitmask >> 1
        return bitaliases

    def __init__(self, val=0):
        self.set(val)
        self._mask = (2 << len(self._bitnames)-1) - 1

    def __str__(self):
        bitmask = 1 << (len(self._bitnames)-1)
        bit_texts = []
        for bitname in self._bitnames:
            if bitname == self._NOT_USED_BITNAME_ID:
                continue
            bit_texts.append("%s:%d" %
                             (bitname, 1 if self._val & bitmask else 0))
            bitmask = bitmask >> 1
        return " ".join(bit_texts)

    def __repr__(self):
        return "<%s 0x%x @%x>" % (self.__class__.__name__, self._val, id(self), )

    def __getattr__(self, name):
        mask = self._bitaliases.get(name)
        if mask is None:
            return super().__getattr__(name)
        return 1 if self._val & mask else 0  # or return self.val & mask

    def __setattr__(self, name,  value):
        mask = self._bitaliases.get(name)
        if mask is None:
            return super().__setattr__(name, value)
        # Setting bits
        if value:
            self._val |= mask
        else:
            self._val &= (self._mask - mask)

    def set(self, val):
        if val < 0:
            raise ValueError("Negative values not allowed")
        if val > 2 << len(self._bitnames):
            raise ValueError(
                "Value: %r too big to fit into bits: %r",  val,  self._bitnames)
        self._val = val

    def __int__(self):
        return self._val

    # Mask operators
    def __iand__(self, other):
        self._val &= int(other)

    def __ixor__(self, other):
        mask = int(other) & self._mask
        self._val ^= mask

    def __ior__(self, other):
        mask = int(other) & self._mask
        self._val |= mask


if __name__ == "__main__":
    import logging
    # Run as:
    #   python3 -m rpi_i2c_chips.register

    logging.basicConfig(
        level=logging.DEBUG, format='%(relativeCreated)6d %(threadName)s %(message)s')
    # Some simple testing

    if 1:
        class Test_Register(Register):
            _bitnames = Register.parse_bitnames(
                "BANK MIRROR SEQOP _ _ ODR INTPOL INTCC")
            _bitaliases = Register.parse_bitaliases(_bitnames)

        class TestNum_Register(Register):
            _bitnames = Register.gen_bitnames(16, prefix="D")
            _bitaliases = Register.parse_bitaliases(_bitnames)

        reg = Test_Register(0x80 | 0x4)  # BANK ODR set
        print ("reg: %s" % (reg, ))
        print ("reg: 0x%02x reg.BANK: %s reg.MIRROR: %s " %
               (int(reg), reg.BANK, reg.MIRROR))

        reg = TestNum_Register(0xf00f)
        print ("reg: %s" % (reg, ))
        print ("reg: 0x%04x reg.D12: %s reg.D11: %s " %
               (int(reg), reg.D12, reg.D11))

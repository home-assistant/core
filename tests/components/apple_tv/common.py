"""Test code shared between test files."""

from pyatv import conf, interface
from pyatv.const import Protocol


class MockPairingHandler(interface.PairingHandler):
    """Mock for PairingHandler in pyatv."""

    def __init__(self, *args):
        """Initialize a new MockPairingHandler."""
        super().__init__(*args)
        self.pin_code = None
        self.paired = False
        self.always_fail = False

    def pin(self, pin):
        """Pin code used for pairing."""
        self.pin_code = pin
        self.paired = False

    @property
    def device_provides_pin(self):
        """Return True if remote device presents PIN code, else False."""
        return self.service.protocol in [Protocol.MRP, Protocol.AirPlay]

    @property
    def has_paired(self):
        """If a successful pairing has been performed.

        The value will be reset when stop() is called.
        """
        return not self.always_fail and self.paired

    async def begin(self):
        """Start pairing process."""

    async def finish(self):
        """Stop pairing process."""
        self.paired = True
        self.service.credentials = self.service.protocol.name.lower() + "_creds"


def create_conf(name, address, *services):
    """Create an Apple TV configuration."""
    atv = conf.AppleTV(name, address)
    for service in services:
        atv.add_service(service)
    return atv

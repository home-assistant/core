"""Mock devices object to test Insteon."""
import logging

from pyinsteon.address import Address
from pyinsteon.device_types import (
    GeneralController_MiniRemote_4,
    Hub,
    SwitchedLightingControl_SwitchLinc,
)

from tests.async_mock import AsyncMock, MagicMock

_LOGGER = logging.getLogger(__name__)


class MockSwitchLinc(SwitchedLightingControl_SwitchLinc):
    """Mock SwitchLinc device."""

    @property
    def operating_flags(self):
        """Return no operating flags to force properties to be checked."""
        return {}


class MockDevices:
    """Mock devices class."""

    def __init__(self, connected=True):
        """Init the MockDevices class."""
        self._devices = {}
        self.modem = None
        self._connected = connected
        self.async_save = AsyncMock()
        self.add_x10_device = MagicMock()
        self.set_id = MagicMock()

    def __getitem__(self, address):
        """Return a a device from the device address."""
        return self._devices.get(address)

    def __iter__(self):
        """Return an iterator of device addresses."""
        yield from self._devices

    def __len__(self):
        """Return the number of devices."""
        return len(self._devices)

    def get(self, address):
        """Return a device from an address or None if not found."""
        return self._devices.get(Address(address))

    async def async_load(self, *args, **kwargs):
        """Load the mock devices."""
        if self._connected:
            addr0 = Address("AA.AA.AA")
            addr1 = Address("11.11.11")
            addr2 = Address("22.22.22")
            addr3 = Address("33.33.33")
            self._devices[addr0] = Hub(addr0)
            self._devices[addr1] = MockSwitchLinc(addr1, 0x02, 0x00)
            self._devices[addr2] = GeneralController_MiniRemote_4(addr2, 0x00, 0x00)
            self._devices[addr3] = SwitchedLightingControl_SwitchLinc(addr3, 0x02, 0x00)
            for device in [self._devices[addr] for addr in [addr1, addr2, addr3]]:
                device.async_read_config = AsyncMock()
            for device in [self._devices[addr] for addr in [addr2, addr3]]:
                device.async_status = AsyncMock()
            self._devices[addr1].async_status = AsyncMock(side_effect=AttributeError)
            self.modem = self._devices[addr0]

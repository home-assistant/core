"""Common code for tplink."""

from typing import Union

from pyHS100 import SmartBulb, SmartPlug


class _DiscoverySource:
    pass


class _ConfigSource:
    pass


SOURCE_DISCOVERY = _DiscoverySource()
SOURCE_CONFIG = _ConfigSource()
DeviceType = Union[SmartBulb, SmartPlug]
DeviceSource = Union[_ConfigSource, _DiscoverySource]


class TPLinkDevice:
    """Wrapper class that holds meta-data about the device."""

    def __init__(self, dev: DeviceType, source: DeviceSource):
        """Initialize the device."""
        self._dev = dev
        self._source = source

    @property
    def dev(self):
        """Underlying device."""
        return self._dev

    @property
    def source(self) -> DeviceSource:
        """Provide the configuration source."""
        return self._source

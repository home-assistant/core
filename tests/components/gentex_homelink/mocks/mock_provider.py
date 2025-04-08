"""Mock class for homelink Providers."""

from .mock_device import MockDevice


class MockProvider:
    """Mock the data provider for Homelink."""

    def __init__(self, *_args, **_kwargs) -> None:
        """Initialize the provider."""
        self.enable_calls = 0
        self.discover_calls = 0
        self.discover_responses = [[MockDevice()], [MockDevice(name="TestDevice2")]]
        self.listeners = []

    def _call_listeners(self, data):
        for listener in self.listeners:
            listener("TOPIC", {"type": "state", "data": data})

    async def enable(self, _sslContext=None):
        """Enable the provider."""

    async def disable(self):
        """Disable the provider."""

    async def discover(self):
        """Discover the available devices."""
        rsp = self.discover_responses[self.discover_calls]
        self.discover_calls += 1
        return rsp

    def listen(self, cb):
        """Register a listener."""
        self.listeners.append(cb)

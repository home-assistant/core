"""Adapter to wrap the pyjuicenet api for home assistant."""


class JuiceNetApi:
    """Represent a connection to JuiceNet."""

    def __init__(self, api):
        """Create an object from the provided API instance."""
        self.api = api
        self._devices = []

    async def setup(self):
        """JuiceNet device setup."""
        self._devices = await self.api.get_devices()

    @property
    def devices(self) -> list:
        """Get a list of devices managed by this account."""
        return self._devices

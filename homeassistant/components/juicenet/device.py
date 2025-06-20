"""Adapter to wrap the pyjuicenet api for home assistant."""

from pyjuicenet import Api, Charger


class JuiceNetApi:
    """Represent a connection to JuiceNet."""

    def __init__(self, api: Api) -> None:
        """Create an object from the provided API instance."""
        self.api = api
        self._devices: list[Charger] = []

    async def setup(self) -> None:
        """JuiceNet device setup."""
        self._devices = await self.api.get_devices()

    @property
    def devices(self) -> list[Charger]:
        """Get a list of devices managed by this account."""
        return self._devices

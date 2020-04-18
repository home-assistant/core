"""Adapter to wrap the pyjuicenet api for home assistant."""

import logging

_LOGGER = logging.getLogger(__name__)


class JuiceNetApi:
    """Represent a connection to JuiceNet."""

    def __init__(self, api, config_entry):
        """Create an object from the provided API instance."""
        self.api = api
        self.config_entry = config_entry
        self._devices = []

    def setup(self, hass):
        """JuiceNet device setup."""
        self._devices = self.api.get_devices()

    @property
    def devices(self) -> list:
        """Get a list of devices managed by this account."""
        return self._devices
